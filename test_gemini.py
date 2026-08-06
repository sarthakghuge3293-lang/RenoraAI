from services.gemini_service import generate_response

print("===== Gemini Test =====")

user_input = input("You : ")

reply = generate_response(user_input)

print("\nGemini :")
print(reply)