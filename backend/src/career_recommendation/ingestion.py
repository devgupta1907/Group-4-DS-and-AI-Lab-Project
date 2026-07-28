import pandas as pd
from tqdm import tqdm
from langchain_core.documents import Document
from langchain_chroma import Chroma

# 1. Import from our new centralized architecture
from core.config import GlobalConfig
from services.llm_client import embeddings
from career_recommendation.config import CareerRecommendationModuleConfig



def prepare_documents(csv_path: str) -> list[Document]:
    """
    Reads the processed ESCO CSV, groups skills by occupation, 
    and returns a list of LangChain Document objects.
    """
    print(f"Reading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    print("Grouping skills by occupation...")
    grouped = df.groupby(['occupation_title', 'occupationUri'])['skill_title'].apply(
        lambda x: ', '.join(x.dropna().unique())
    ).reset_index()
    
    docs = []
    for _, row in grouped.iterrows():
        title = row['occupation_title']
        skills = row['skill_title']
        uri = row['occupationUri']
        
        text_payload = f"Occupation Title: {title}\nCore Skills: {skills}"
        metadata = {
            "occupation_title": title,
            "occupation_uri": uri
        }
        docs.append(Document(page_content=text_payload, metadata=metadata))
        
    return docs



# def build_vector_store():
#     """
#     Vectorizes the documents using the centralized Gemini embeddings 
#     and stores them in ChromaDB.
#     """
#     # 2. Use the CareerRecommendationModuleConfig for the specific dataset path
#     docs = prepare_documents(CareerRecommendationModuleConfig.ESCO_DATA_PATH)
#     print(f"Prepared {len(docs)} unique atomic occupation chunks.")
    
#     print("Initializing ChromaDB and embedding documents (This may take a few minutes)...")
    
#     # 3. Use the centralized embeddings instance and GlobalConfig database path
#     vectorstore = Chroma.from_documents(
#         documents=docs,
#         embedding=embeddings,
#         persist_directory=GlobalConfig.CHROMA_DB_DIR
#     )
    
#     print(f"Success! Vector Store built and persisted at: {GlobalConfig.CHROMA_DB_DIR}")

from tqdm import tqdm # Add this to the very top of your imports

def build_vector_store():
    """
    Vectorizes the documents using the centralized embeddings 
    and stores them in ChromaDB in batches with a progress bar.
    """
    docs = prepare_documents(CareerRecommendationModuleConfig.ESCO_DATA_PATH)
    print(f"Prepared {len(docs)} unique atomic occupation chunks.")
    
    print("Initializing empty ChromaDB...")
    # Initialize the DB connection first
    vectorstore = Chroma(
        embedding_function=embeddings,
        persist_directory=GlobalConfig.CHROMA_DB_DIR
    )
    
    # Batch processing parameters
    batch_size = 100
    total_batches = (len(docs) + batch_size - 1) // batch_size
    
    print("Starting embedding process...")
    # Process and add documents in batches with a progress bar
    for i in tqdm(range(0, len(docs), batch_size), total=total_batches, desc="Embedding Chunks"):
        batch = docs[i : i + batch_size]
        vectorstore.add_documents(batch)
        
    print(f"\nSuccess! Vector Store built and persisted at: {GlobalConfig.CHROMA_DB_DIR}")

if __name__ == "__main__":
    build_vector_store()