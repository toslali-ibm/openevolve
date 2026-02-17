package main

import (
	"fmt"
	"os"
)

func main() {
	// Run the game and print the score
	score := PlayGame()

	// Output score for OpenEvolve to parse
	fmt.Printf("SCORE: %d\n", score)

	// Exit with 0 for success
	os.Exit(0)
}

// PlayGame runs the game and returns the score
func PlayGame() int {
	// Get strategy's guesses
	guesses := GetStrategy()

	// Evaluate the strategy
	return EvaluateStrategy(guesses)
}
