import asyncio
import os
import uuid
import logging
import time
from dataclasses import dataclass

from openevolve.database import Program, ProgramDatabase
from openevolve.config import Config
from openevolve.evaluator import Evaluator
from openevolve.llm.ensemble import LLMEnsemble
from openevolve.prompt.sampler import PromptSampler
from openevolve.hypothesis import (
    rescue_hypotheses,
    inject_result_comments,
    count_hypothesis_comments,
    count_expect_comments,
    count_result_comments,
    IterationHypothesisStats,
)
from openevolve.tuning import tune_program, IterationTuningStats
from openevolve.utils.code_utils import (
    apply_diff,
    extract_diffs,
    format_diff_summary,
    parse_full_rewrite,
)


@dataclass
class Result:
    """Resulting program and metrics from an iteration of OpenEvolve"""

    child_program: str = None
    parent: str = None
    child_metrics: str = None
    iteration_time: float = None
    prompt: str = None
    llm_response: str = None
    artifacts: dict = None
    hypothesis_stats: IterationHypothesisStats = None
    tuning_stats: IterationTuningStats = None


async def run_iteration_with_shared_db(
    iteration: int,
    config: Config,
    database: ProgramDatabase,
    evaluator: Evaluator,
    llm_ensemble: LLMEnsemble,
    prompt_sampler: PromptSampler,
):
    """
    Run a single iteration using shared memory database

    This is optimized for use with persistent worker processes.
    """
    logger = logging.getLogger(__name__)

    try:
        # Sample parent and inspirations from database
        parent, inspirations = database.sample(num_inspirations=config.prompt.num_top_programs)

        # Get artifacts for the parent program if available
        parent_artifacts = database.get_artifacts(parent.id)

        # Get island-specific top programs for prompt context (maintain island isolation)
        parent_island = parent.metadata.get("island", database.current_island)
        island_top_programs = database.get_top_programs(5, island_idx=parent_island)
        island_previous_programs = database.get_top_programs(3, island_idx=parent_island)

        # Build prompt
        prompt = prompt_sampler.build_prompt(
            current_program=parent.code,
            parent_program=parent.code,
            program_metrics=parent.metrics,
            previous_programs=[p.to_dict() for p in island_previous_programs],
            top_programs=[p.to_dict() for p in island_top_programs],
            inspirations=[p.to_dict() for p in inspirations],
            language=config.language,
            evolution_round=iteration,
            diff_based_evolution=config.diff_based_evolution,
            program_artifacts=parent_artifacts if parent_artifacts else None,
            feature_dimensions=database.config.feature_dimensions,
            hypothesis_driven=config.hypothesis_driven,
            tuning_enabled=config.tuning.enabled,
        )

        result = Result(parent=parent)
        iteration_start = time.time()

        # Track hypothesis pipeline stats (treatment only, but cheap for control too)
        hypo_stats = IterationHypothesisStats(iteration=iteration)

        if config.hypothesis_driven:
            # Track: hypotheses visible in parent program
            hypo_stats.hypotheses_in_parent = count_hypothesis_comments(parent.code)
            hypo_stats.results_in_parent = count_result_comments(parent.code)
            # Track: how many top programs have hypotheses
            hypo_stats.top_programs_total = len(island_top_programs)
            hypo_stats.top_programs_with_hypotheses = sum(
                1 for p in island_top_programs if count_hypothesis_comments(p.code) > 0
            )

        # Generate code modification
        llm_response = await llm_ensemble.generate_with_context(
            system_message=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
        )

        # Track: hypotheses in raw LLM response
        if config.hypothesis_driven and llm_response:
            hypo_stats.hypotheses_in_llm_response = count_hypothesis_comments(llm_response)
            hypo_stats.expects_in_llm_response = count_expect_comments(llm_response)

        # Parse the response
        if config.diff_based_evolution:
            diff_blocks = extract_diffs(llm_response, config.diff_pattern)

            if not diff_blocks:
                logger.warning(f"Iteration {iteration+1}: No valid diffs found in response")
                return None

            # Apply the diffs
            child_code = apply_diff(parent.code, llm_response, config.diff_pattern)
            # Rescue hypothesis comments that the LLM placed outside diff blocks
            if config.hypothesis_driven:
                child_code = rescue_hypotheses(child_code, llm_response)
            changes_summary = format_diff_summary(diff_blocks)
        else:
            # Parse full rewrite
            new_code = parse_full_rewrite(llm_response, config.language)

            if not new_code:
                logger.warning(f"Iteration {iteration+1}: No valid code found in response")
                return None

            # Rescue hypothesis comments from LLM response into code
            if config.hypothesis_driven:
                new_code = rescue_hypotheses(new_code, llm_response)

            child_code = new_code
            changes_summary = "Full rewrite"

        # Track: hypotheses persisted in child code (after rescue)
        if config.hypothesis_driven:
            hypo_stats.hypotheses_in_child_code = count_hypothesis_comments(child_code)
            hypo_stats.expects_in_child_code = count_expect_comments(child_code)

        # Check code length
        if len(child_code) > config.max_code_length:
            logger.warning(
                f"Iteration {iteration+1}: Generated code exceeds maximum length "
                f"({len(child_code)} > {config.max_code_length})"
            )
            return None

        # Tune thresholds if enabled
        if config.tuning.enabled:
            try:
                child_code, tuning_stats = await tune_program(
                    child_code,
                    evaluator.evaluate_program,
                    config.tuning,
                )
                tuning_stats.iteration = iteration
                result.tuning_stats = tuning_stats
            except ImportError as e:
                logger.error(f"[TUNING] {e}")
                return None
            except Exception as e:
                logger.warning(f"[TUNING] Tuning failed, using original code: {e}")

        # Evaluate the child program
        child_id = str(uuid.uuid4())
        result.child_metrics = await evaluator.evaluate_program(child_code, child_id)

        # Stamp hypothesis verdicts into child code
        if config.hypothesis_driven and result.child_metrics:
            results_before = count_result_comments(child_code)
            child_code = inject_result_comments(child_code, result.child_metrics)
            results_after = count_result_comments(child_code)
            hypo_stats.results_injected = results_after - results_before

        # Handle artifacts if they exist
        artifacts = evaluator.get_pending_artifacts(child_id)

        # Set template_key of Prompts
        template_key = "full_rewrite_user" if not config.diff_based_evolution else "diff_user"

        # Create a child program
        result.child_program = Program(
            id=child_id,
            code=child_code,
            language=config.language,
            parent_id=parent.id,
            generation=parent.generation + 1,
            metrics=result.child_metrics,
            iteration_found=iteration,
            metadata={
                "changes": changes_summary,
                "parent_metrics": parent.metrics,
            },
            prompts=(
                {
                    template_key: {
                        "system": prompt["system"],
                        "user": prompt["user"],
                        "responses": [llm_response] if llm_response is not None else [],
                    }
                }
                if database.config.log_prompts
                else None
            ),
        )

        result.prompt = prompt
        result.llm_response = llm_response
        result.artifacts = artifacts
        result.hypothesis_stats = hypo_stats
        result.iteration_time = time.time() - iteration_start
        result.iteration = iteration

        return result

    except Exception as e:
        logger.exception(f"Error in iteration {iteration}: {e}")
        return None
