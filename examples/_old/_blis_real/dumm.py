def read_prompts(path):
    with open(path, "r") as f:
        text = f.read()

    prompts = [
        p.strip()
        for p in text.split("\n\n")
        if p.strip()
    ]

    return prompts

prompts = read_prompts("promptsblisopenevolve.txt") 

print(prompts[1])