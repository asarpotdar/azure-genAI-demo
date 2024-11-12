from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

def retrieve_relevant_documents(query):
    search_endpoint = "https://helphubsearch.search.windows.net"
    search_api_key = "<>"
    index_name = "azureblob-index"
    
    # Create the client to interact with Azure Cognitive Search
    client = SearchClient(endpoint=search_endpoint,
                          index_name=index_name,
                          credential=AzureKeyCredential(search_api_key))
    
    # Query the search index
    results = client.search(query)
    
    # Extract the top results
    relevant_documents = [result['content'] for result in results]
    
    return relevant_documents

# Example usage
query = "how to open new account"
relevant_docs = retrieve_relevant_documents(query)
print(relevant_docs)
