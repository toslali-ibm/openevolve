package main

import "math"

// EvaluateStrategy evaluates how good the strategy's guesses are
// Goal: Find numbers that maximize the scoring function
// Scoring function: sum of (100 - abs(guess - target))
func EvaluateStrategy(guesses []int) int {
	// Target numbers that give maximum score
	targets := []int{25, 50, 75}

	score := 0
	for i := 0; i < len(guesses) && i < len(targets); i++ {
		// Calculate distance from target
		distance := int(math.Abs(float64(guesses[i] - targets[i])))

		// Score is higher when closer to target
		pointValue := 100 - distance
		if pointValue < 0 {
			pointValue = 0
		}

		score += pointValue
	}

	return score
}
