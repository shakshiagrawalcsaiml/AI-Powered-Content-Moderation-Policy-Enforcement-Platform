from transformers import pipeline

# Load the same model
classifier = pipeline(
    model="unitary/toxic-bert",
    return_all_scores=True
)

# Test with the problematic text
result = classifier("i hate you")

print("Full result:", result)
print("\nType of result:", type(result))
print("\nFirst element:", result[0])
print("\nType of first element:", type(result[0]))
s
# Try to extract scores
scores = result[0]
for item in scores:
    print(f"\nItem: {item}")
    print(f"Label: {item.get('label')}, Score: {item.get('score')}")
