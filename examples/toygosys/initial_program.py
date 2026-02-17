"""
Initial Go Strategy Program for OpenEvolve

This file contains the Go code for the strategy module that will be evolved.
OpenEvolve will modify the EVOLVE-BLOCK section to improve the strategy.
"""

# The Go code as a Python string
GO_STRATEGY_CODE = """package main

// GetStrategy returns the strategy's guesses
// This is the module that OpenEvolve will evolve
func GetStrategy() []int {
	// EVOLVE-BLOCK-START
	// Initial naive strategy: just return some random numbers
	guesses := []int{10, 20, 30}
	// EVOLVE-BLOCK-END

	return guesses
}
"""
