import truststore
truststore.inject_into_ssl()

from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
llm=ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0,thinking_level="minimal")
response=llm.invoke("האם המייל הבא הוא פרסומת? ענה כן או לא: מבצע ענק! 50% הנחה על כל החנות רק היום")
print(response.text)