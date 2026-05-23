import sys
import os
from kaggle_environments import make

def main():
    agent_path = "families/hybrid/agents/generated/hybrid_v009_dna.py"
    opponent_path = "agents/versions/auto_v009_20260522_234815_auto_r0037_077_elite_auto_r0020_009_elite_auto_r0017_014_elite_auto_r0016_004_champion_template.py"
    
    if not os.path.exists(agent_path):
        print(f"Error: {agent_path} does not exist.")
        sys.exit(1)
    if not os.path.exists(opponent_path):
        print(f"Error: {opponent_path} does not exist.")
        sys.exit(1)
        
    print(f"Running match between {agent_path} and {opponent_path} in debug mode...")
    
    env = make("orbit_wars", configuration={"seed": 42}, debug=True)
    env.run([agent_path, opponent_path])
    
    steps = env.steps
    final = steps[-1]
    a = final[0]
    b = final[1]
    
    print("\n--- Match Results ---")
    print(f"Agent A Status: {a.status}")
    print(f"Agent B Status: {b.status}")
    print(f"Agent A Reward: {a.reward}")
    print(f"Agent B Reward: {b.reward}")
    
    # Check if there is a traceback recorded in step outputs
    for i, step in enumerate(steps):
        for player_idx, action_record in enumerate(step):
            if action_record.status == "ERROR":
                print(f"\n[ERROR] Player {player_idx} encountered an error at step {i}:")
                print(f"Status: {action_record.status}")
                print(f"Message: {action_record.message}")
                
if __name__ == "__main__":
    main()
