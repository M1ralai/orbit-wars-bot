from kaggle_environments import make

wins = 0
losses = 0
draws = 0
errors = 0

for seed in range(50):
    env = make("orbit_wars", configuration={"seed": seed}, debug=False)
    env.run(["main.py", "random"])

    final = env.steps[-1]
    me = final[0]

    if me.status != "DONE":
        errors += 1
    elif me.reward == 1:
        wins += 1
    elif me.reward == -1:
        losses += 1
    else:
        draws += 1

print("wins:", wins)
print("losses:", losses)
print("draws:", draws)
print("errors:", errors)
print("winrate:", wins / 50)
