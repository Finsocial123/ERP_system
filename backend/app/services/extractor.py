# from dotenv import load_dotenv

# load_dotenv()

# from pathlib import Path
# from langchain_community.document_loaders import PyPDFLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_qdrant import QdrantVectorStore


# pdf_path = Path(__file__).parent / "nodejs.pdf"

# #load this file in python program
# loader = PyPDFLoader(pdf_path)
# docs = loader.load()


# #Split the docs into smaller chunks
# text_splitter = RecursiveCharacterTextSplitter(
#     chunk_size=1000,
#     chunk_overlap=400    #get some content from previous chunks to add more context
# )

# chunks = text_splitter.split_documents(documents=docs)

# embedding_model = CohereEmbeddings(
#     model="embed-v4.0",
#     cohere_api_key=""
# )

# vector_store = QdrantVectorStore.from_documents(
#     documents=chunks,
#     embedding=embedding_model,
#     url="http://localhost:6333",
#     collection_name="learning_rag",
# )

# print("Indexing of documents done")


import io
from pypdf import PdfReader
import re

def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))

    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())

    full_text = "\n\n".join(pages)
    return clean_text(full_text)

def clean_text(text: str) -> str:
    """Remove common PDF artifacts"""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)
    return text.strip()