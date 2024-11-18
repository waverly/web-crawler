#  out of use after migrating to openai

# import unittest
# from unittest.mock import patch, MagicMock
# from src.web_crawler.gemini_analyzer import analyze_page_content, init_gemini


# class TestGeminiAnalyzer(unittest.TestCase):
#     def setUp(self):
#         self.test_links = [
#             {
#                 "url": "https://example.com/1",
#                 "title": "Test Title 1",
#                 "link_text": "Link 1",
#                 "context": "Some context 1",
#             },
#             {
#                 "url": "https://example.com/2",
#                 "title": "Test Title 2",
#                 "link_text": "Link 2",
#                 "context": "Some context 2",
#             },
#         ]
#         self.high_priority_keywords = ["important", "critical"]
#         self.medium_priority_keywords = ["useful", "helpful"]

#     @patch("google.generativeai.GenerativeModel")
#     @patch("google.generativeai.configure")
#     def test_init_gemini(self, mock_configure, mock_model):
#         mock_model_instance = MagicMock()
#         mock_model.return_value = mock_model_instance

#         model = init_gemini()

#         mock_configure.assert_called_once()
#         mock_model.assert_called_once_with("gemini-1.5-flash")
#         self.assertEqual(model, mock_model_instance)

#     @patch("src.web_crawler.gemini_analyzer.init_gemini")
#     def test_analyze_page_content(self, mock_init_gemini):
#         mock_response = MagicMock()
#         mock_response.text = """
#         {
#             "links": [
#                 {
#                     "url": "https://example.com/1",
#                     "title": "Test Title 1",
#                     "relevancy": 0.8,
#                     "relevancy_explanation": "Contains high priority keywords",
#                     "high_priority_keywords": ["important"],
#                     "medium_priority_keywords": ["useful"]
#                 },
#                 {
#                     "url": "https://example.com/2",
#                     "title": "Test Title 2",
#                     "relevancy": 0.5,
#                     "relevancy_explanation": "Contains medium priority keywords",
#                     "high_priority_keywords": [],
#                     "medium_priority_keywords": ["helpful"]
#                 }
#             ]
#         }
#         """

#         mock_model = MagicMock()
#         mock_model.generate_content.return_value = mock_response
#         mock_init_gemini.return_value = mock_model

#         results = analyze_page_content(
#             self.test_links, self.high_priority_keywords, self.medium_priority_keywords, test_mode=True
#         )

#         self.assertEqual(len(results), 2)
#         self.assertEqual(results[0]["url"], "https://example.com/1")
#         self.assertEqual(results[0]["relevancy"], 0.8)
#         self.assertEqual(results[1]["url"], "https://example.com/2")
#         self.assertEqual(results[1]["relevancy"], 0.5)

#     @patch("src.web_crawler.gemini_analyzer.init_gemini")
#     def test_analyze_page_content_empty_response(self, mock_init_gemini):
#         mock_response = MagicMock()
#         mock_response.text = ""

#         mock_model = MagicMock()
#         mock_model.generate_content.return_value = mock_response
#         mock_init_gemini.return_value = mock_model

#         results = analyze_page_content(
#             self.test_links, self.high_priority_keywords, self.medium_priority_keywords, test_mode=True
#         )

#         self.assertEqual(results, [])

#     @patch("src.web_crawler.gemini_analyzer.init_gemini")
#     def test_analyze_page_content_invalid_json(self, mock_init_gemini):
#         mock_response = MagicMock()
#         mock_response.text = "Invalid JSON"

#         mock_model = MagicMock()
#         mock_model.generate_content.return_value = mock_response
#         mock_init_gemini.return_value = mock_model

#         results = analyze_page_content(
#             self.test_links, self.high_priority_keywords, self.medium_priority_keywords, test_mode=True
#         )

#         self.assertEqual(results, [])

#     @patch("src.web_crawler.gemini_analyzer.init_gemini")
#     def test_analyze_page_content_no_links_key(self, mock_init_gemini):
#         mock_response = MagicMock()
#         mock_response.text = """
#         {
#             "data": []
#         }
#         """

#         mock_model = MagicMock()
#         mock_model.generate_content.return_value = mock_response
#         mock_init_gemini.return_value = mock_model

#         results = analyze_page_content(
#             self.test_links, self.high_priority_keywords, self.medium_priority_keywords, test_mode=True
#         )

#         self.assertEqual(results, [])

#     @patch("src.web_crawler.gemini_analyzer.init_gemini")
#     def test_analyze_page_content_links_not_list(self, mock_init_gemini):
#         mock_response = MagicMock()
#         mock_response.text = """
#         {
#             "links": "Not a list"
#         }
#         """

#         mock_model = MagicMock()
#         mock_model.generate_content.return_value = mock_response
#         mock_init_gemini.return_value = mock_model

#         results = analyze_page_content(
#             self.test_links, self.high_priority_keywords, self.medium_priority_keywords, test_mode=True
#         )

#         self.assertEqual(results, [])

#     @patch("src.web_crawler.gemini_analyzer.init_gemini")
#     def test_analyze_page_content_generate_exception(self, mock_init_gemini):
#         mock_model = MagicMock()
#         mock_model.generate_content.side_effect = Exception("API Error")
#         mock_init_gemini.return_value = mock_model

#         results = analyze_page_content(
#             self.test_links, self.high_priority_keywords, self.medium_priority_keywords, test_mode=True
#         )

#         self.assertEqual(results, [])

#     @patch("src.web_crawler.gemini_analyzer.init_gemini")
#     def test_analyze_page_content_partial_success(self, mock_init_gemini):
#         # Create 6 test links that will be processed in 3 batches of 2
#         links = self.test_links * 3  # Total 6 links

#         # First batch - successful response with 2 links
#         mock_response1 = MagicMock()
#         mock_response1.text = """
#         {
#             "links": [
#                 {
#                     "url": "https://example.com/1",
#                     "title": "Test Title 1",
#                     "relevancy": 0.8,
#                     "relevancy_explanation": "Contains high priority keywords",
#                     "high_priority_keywords": ["important"],
#                     "medium_priority_keywords": ["useful"],
#                     "context": ""
#                 },
#                 {
#                     "url": "https://example.com/2",
#                     "title": "Test Title 2",
#                     "relevancy": 0.5,
#                     "relevancy_explanation": "Contains medium priority keywords",
#                     "high_priority_keywords": [],
#                     "medium_priority_keywords": ["helpful"],
#                     "context": ""
#                 }
#             ]
#         }
#         """

#         # Second batch - API error
#         # Third batch - successful response with 2 more links
#         mock_response3 = MagicMock()
#         mock_response3.text = """
#         {
#             "links": [
#                 {
#                     "url": "https://example.com/5",
#                     "title": "Test Title 5",
#                     "relevancy": 0.9,
#                     "relevancy_explanation": "Highly relevant",
#                     "high_priority_keywords": ["important"],
#                     "medium_priority_keywords": [],
#                     "context": ""
#                 },
#                 {
#                     "url": "https://example.com/6",
#                     "title": "Test Title 6",
#                     "relevancy": 0.4,
#                     "relevancy_explanation": "Less relevant",
#                     "high_priority_keywords": [],
#                     "medium_priority_keywords": ["helpful"],
#                     "context": ""
#                 }
#             ]
#         }
#         """

#         mock_model = MagicMock()
#         # Mock responses for the 3 batches
#         mock_model.generate_content.side_effect = [mock_response1, Exception("API Error"), mock_response3]
#         mock_init_gemini.return_value = mock_model

#         with patch("src.web_crawler.gemini_analyzer.config.GEMINI_BATCH_SIZE", 2):
#             results = analyze_page_content(
#                 links, self.high_priority_keywords, self.medium_priority_keywords, test_mode=False
#             )

#         # Should get 4 results total (2 from first batch + 0 from failed batch + 2 from last batch)
#         self.assertEqual(len(results), 4)

#         # Verify first batch results
#         self.assertEqual(results[0]["url"], "https://example.com/1")
#         self.assertEqual(results[1]["url"], "https://example.com/2")

#         # Verify third batch results
#         self.assertEqual(results[2]["url"], "https://example.com/5")
#         self.assertEqual(results[3]["url"], "https://example.com/6")

#         # Verify the model was called 3 times (once per batch)
#         self.assertEqual(mock_model.generate_content.call_count, 3)


# if __name__ == "__main__":
#     unittest.main()
