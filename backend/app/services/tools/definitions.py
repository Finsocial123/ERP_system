# TOOLS = [
#     {
#         "type": "function",
#         "function": {
#             "name": "quiz_generator",
#             "description": "Generate a multiple choice quiz for a lesson. Call this when the student asks to be tested or quizzed on a lesson.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "lesson_id": {
#                         "type": "integer",
#                         "description": "The ID of the lesson to generate quiz questions from"
#                     },
#                     "num_questions": {
#                         "type": "integer",
#                         "description": "Number of questions to generate. Default is 5.",
#                         "default": 5
#                     },
#                     "difficulty": {
#                         "type": "string",
#                         "enum": ["easy", "medium", "hard"],
#                         "default": "medium"
#                     }
#                 },
#                 "required": ["lesson_id"]
#             }
#         }
#     },
# ]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for current information. Use this for questions about current versions, recent news, or anything not in the course material.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The exact search query to look up. Example: 'FastAPI latest version 2025'"
                    }
                },
                "required": ["query"]
            }
        }
    }   
]