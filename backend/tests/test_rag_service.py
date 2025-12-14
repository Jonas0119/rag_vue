"""
RAG Service Unit Tests
"""
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.rag_service import RAGService
from langchain_core.documents import Document

class TestRAGService(unittest.TestCase):
    
    @patch('backend.services.rag_service.get_vector_store_service')
    @patch('backend.services.rag_service.ChatAnthropic')
    def setUp(self, mock_llm, mock_get_vector_service):
        self.mock_vector_service = MagicMock()
        mock_get_vector_service.return_value = self.mock_vector_service
        
        self.mock_llm_instance = MagicMock()
        mock_llm.return_value = self.mock_llm_instance
        
        # Mock config
        with patch('services.rag_service.config') as mock_config:
            mock_config.ANTHROPIC_API_KEY = "test_key"
            mock_config.ANTHROPIC_BASE_URL = "test_url"
            mock_config.LLM_MODEL = "test_model"
            mock_config.LLM_TEMPERATURE = 0
            mock_config.LLM_MAX_TOKENS = 100
            mock_config.RAG_FALLBACK_ENABLED = True
            mock_config.RAG_SIMILARITY_THRESHOLD = 0.5
            
            self.rag_service = RAGService()

    def test_query_no_docs_fallback(self):
        """Test fallback when no documents are found"""
        # Setup mock to return no documents
        self.mock_vector_service.search_with_score.return_value = []
        
        # Setup LLM response for direct answer
        self.mock_llm_instance.invoke.return_value = "Direct answer"
        
        # Mock the chain
        with patch('langchain_core.runnables.RunnableSequence.invoke') as mock_chain_invoke:
            mock_chain_invoke.return_value = "Direct answer"
            
            result = self.rag_service.query(user_id=1, question="test")
            
            self.assertTrue(result['fallback_mode'])
            self.assertEqual(result['fallback_reason'], "未找到相关文档")
            self.assertEqual(result['answer'], "Direct answer")

    def test_query_low_similarity_fallback(self):
        """Test fallback when similarity is too low"""
        # Setup mock to return low similarity document
        # Score 0.8 means similarity 0.2 (since similarity = 1 - score)
        doc = Document(page_content="test content", metadata={})
        self.mock_vector_service.search_with_score.return_value = [(doc, 0.8)]
        
        with patch('langchain_core.runnables.RunnableSequence.invoke') as mock_chain_invoke:
            mock_chain_invoke.return_value = "Direct answer"
            
            result = self.rag_service.query(user_id=1, question="test")
            
            self.assertTrue(result['fallback_mode'])
            self.assertIn("相似度太低", result['fallback_reason'])

    def test_query_success(self):
        """Test successful RAG query"""
        # Setup mock to return high similarity document
        # Score 0.1 means similarity 0.9
        doc = Document(page_content="test content", metadata={})
        self.mock_vector_service.search_with_score.return_value = [(doc, 0.1)]
        
        with patch('langchain_core.runnables.RunnableSequence.invoke') as mock_chain_invoke:
            mock_chain_invoke.return_value = "RAG answer"
            
            result = self.rag_service.query(user_id=1, question="test")
            
            self.assertFalse(result['fallback_mode'])
            self.assertEqual(result['answer'], "RAG answer")
            self.assertEqual(len(result['retrieved_docs']), 1)

if __name__ == '__main__':
    unittest.main()
