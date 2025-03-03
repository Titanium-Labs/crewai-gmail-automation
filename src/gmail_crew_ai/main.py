#!/usr/bin/env python
import sys
import warnings
from dotenv import load_dotenv

from gmail_crew_ai.crew import GmailCrewAi

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

def run():
    """Run the Gmail Crew AI."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Get user input for number of emails to process
        try:
            email_limit = input("How many emails would you like to process? (default: 5): ")
            if email_limit.strip() == "":
                email_limit = 5
            else:
                email_limit = int(email_limit)
                if email_limit <= 0:
                    print("Number must be positive. Using default of 5.")
                    email_limit = 5
        except ValueError:
            print("Invalid input. Using default of 5 emails.")
            email_limit = 5
        
        print(f"Processing {email_limit} emails...")
        
        # Create and run the crew with the specified email limit
        result = GmailCrewAi().crew().kickoff(inputs={'email_limit': email_limit})
        
        # Print the result in a clean way
        if result:
            print("\nCrew execution completed successfully! 🎉")
            print("Results have been saved to the output directory.")
            return 0  # Return success code
        else:
            print("\nCrew execution completed but no results were returned.")
            return 0  # Still consider this a success
    except Exception as e:
        print(f"\nError: {e}")
        return 1  # Return error code

def train():
    """
    Train the crew for a given number of iterations.
    """
    try:
        GmailCrewAi().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2])
        return 0
    except Exception as e:
        print(f"An error occurred while training the crew: {e}")
        return 1

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        GmailCrewAi().crew().replay(task_id=sys.argv[1])
        return 0
    except Exception as e:
        print(f"An error occurred while replaying the crew: {e}")
        return 1

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs"
    }
    try:
        GmailCrewAi().crew().test(n_iterations=int(sys.argv[1]), openai_model_name=sys.argv[2], inputs=inputs)
        return 0
    except Exception as e:
        print(f"An error occurred while testing the crew: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(run())  # Use the return value as the exit code
