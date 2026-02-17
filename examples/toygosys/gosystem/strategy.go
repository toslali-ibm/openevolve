package main

// GetStrategy returns the strategy's guesses
// This is the module that OpenEvolve will evolve
func GetStrategy() []int {
	// EVOLVE-BLOCK-START
	// Initial naive strategy: just return some random numbers
	guesses := []int{10, 20, 30}
	// EVOLVE-BLOCK-END

	return guesses
}
