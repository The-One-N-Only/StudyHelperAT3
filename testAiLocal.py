"""
Local AI Alternative to Claude API
Provides a simple interface for local text generation using HuggingFace models
"""

from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
import torch
from typing import Optional, List, Dict
import json
import warnings

# Suppress transformers warnings
warnings.filterwarnings("ignore", category=UserWarning)

class LocalAIClient:
    """Simple local AI client that mimics Claude API behavior"""
    
    def __init__(self, model_name: str = "distilgpt2"):
        """
        Initialize the local AI client
        
        Args:
            model_name: HuggingFace model identifier. Options:
                - "distilgpt2" (fast, lightweight)
                - "gpt2" (better quality, slower)
                - "mistralai/Mistral-7B" (requires more resources)
        """
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")
        
        try:
            print(f"Loading model: {model_name}...")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForCausalLM.from_pretrained(model_name).to(self.device)
            print(f"Model loaded successfully!")
        except Exception as e:
            print(f"Error loading model: {e}")
            raise
    
    def complete(
        self,
        prompt: str,
        max_length: int = 100,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> str:
        """
        Generate text completion for a prompt
        
        Args:
            prompt: The input text to complete
            max_length: Maximum length of generated text (new tokens)
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling parameter
            
        Returns:
            Generated completion text
        """
        try:
            inputs = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_new_tokens=max_length,  # Use max_new_tokens instead of max_length
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                )
            
            completion = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return completion
        except Exception as e:
            print(f"Error during text generation: {e}")
            raise
    
    def summarize(self, text: str, max_length: int = 50) -> str:
        """
        Summarize text using a summarization prompt
        
        Args:
            text: Text to summarize
            max_length: Maximum length of summary
            
        Returns:
            Summarized text
        """
        prompt = f"Summarize this text in one sentence: {text[:200]}\nSummary:"
        return self.complete(prompt, max_length=max_length)


# Main test/demo
if __name__ == "__main__":
    # Initialize client
    client = LocalAIClient(model_name="distilgpt2")
    
    # Test 1: Simple completion
    print("\n" + "="*50)
    print("Test 1: Text Completion")
    print("="*50)
    prompt = "What are the benefits of open source"
    result = client.complete(prompt, max_length=100)
    print(f"Prompt: {prompt}")
    print(f"Generated: {result}\n")
    
    # Test 2: Question answering
    print("="*50)
    print("Test 2: Question Answering")
    print("="*50)
    qa_prompt = "Question: What is machine learning?\nAnswer:"
    result = client.complete(qa_prompt, max_length=60)
    print(f"Q&A Result: {result}\n")
    
    # Test 3: Summarization
    print("="*50)
    print("Test 3: Summarization")
    print("="*50)
    text_to_summarize = "Machine learning is a subset of artificial intelligence that focuses on the development of algorithms and statistical models that enable computers to improve their performance on tasks through experience rather than being explicitly programmed."
    result = client.summarize(text_to_summarize, max_length=40)
    print(f"Original: {text_to_summarize}")
    print(f"Summary: {result}\n")
    
    print("✓ All tests completed successfully!")
