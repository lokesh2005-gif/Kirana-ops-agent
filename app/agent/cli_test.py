import os
from dotenv import load_dotenv

# Load .env before initializing DB and Agent
load_dotenv()

# We force the db to use sqlite in memory or local file just for CLI testing
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///kirana.db"

from app.db.database import engine
from app.db.models import Base
from app.db.seed import seed_db
from app.agent.agent import get_chat_session

def run_repl():
    print("Setting up DB...")
    Base.metadata.create_all(bind=engine)
    seed_db()
    
    print("Starting Kirana Agent REPL. Type 'exit' to quit.\n")
    chat = get_chat_session()
    
    # Pre-defined test script logic if running automatically
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        inputs = [
            "50 packets of Maggi came in, cost ₹12, MRP ₹14",
            "make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, UPI",
            "drop the butter, make it 6 Maggi",
            "how much sugar is left?",
            "add atta"
        ]
        for user_msg in inputs:
            print(f"\nUser: {user_msg}")
            
            # Retry logic to handle Gemini API rate limits
            max_retries = 3
            import time
            for attempt in range(max_retries):
                try:
                    response = chat.send_message(user_msg)
                    print(f"Agent: {response.text}")
                    break
                except Exception as e:
                    if "429" in str(e):
                        print(f"Rate limited... waiting 35s (Attempt {attempt+1}/{max_retries})")
                        time.sleep(35)
                    else:
                        print(f"Error: {e}")
                        break
        return

    # Interactive loop
    while True:
        try:
            user_msg = input("\nUser: ")
            if user_msg.lower() in ['exit', 'quit']:
                break
            if not user_msg.strip():
                continue
                
            response = chat.send_message(user_msg)
            print(f"Agent: {response.text}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run_repl()
