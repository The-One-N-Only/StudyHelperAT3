/**
 * StudyHelper AI Prompt Module
 * Handles user questions and AI responses using uploaded files and web sources
 */

class StudyHelperAI {
  constructor() {
    this.conversationHistory = [];
    this.currentATN = null;
  }

  /**
   * Ask a single question to the AI
   * @param {string} prompt - The question to ask
   * @param {Object} options - Optional settings
   * @returns {Promise<Object>} The AI response with answer and sources
   */
  async askQuestion(prompt, options = {}) {
    const {
      searchWeb = true,
      atn = this.currentATN
    } = options;

    try {
      const response = await fetch('/api/answer/prompt', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': this.getCSRFToken()
        },
        body: JSON.stringify({
          prompt: prompt,
          search_web: searchWeb,
          atn: atn
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();

      if (!data.status) {
        throw new Error(data.error || 'Failed to get response');
      }

      return data;
    } catch (error) {
      console.error('Question failed:', error);
      return {
        status: false,
        error: error.message
      };
    }
  }

  /**
   * Continue a multi-turn conversation
   * @param {string} userMessage - The user's message
   * @param {Object} options - Optional settings
   * @returns {Promise<Object>} The AI response
   */
  async chat(userMessage, options = {}) {
    const { atn = this.currentATN } = options;

    // Add user message to history
    this.conversationHistory.push({
      role: 'user',
      content: userMessage
    });

    try {
      const response = await fetch('/api/answer/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': this.getCSRFToken()
        },
        body: JSON.stringify({
          messages: this.conversationHistory,
          atn: atn
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();

      if (!data.status) {
        throw new Error(data.error || 'Failed to get response');
      }

      // Add assistant response to history
      this.conversationHistory.push({
        role: 'assistant',
        content: data.response
      });

      return data;
    } catch (error) {
      console.error('Chat failed:', error);
      // Remove the user message since it failed
      this.conversationHistory.pop();
      return {
        status: false,
        error: error.message
      };
    }
  }

  /**
   * Set the current assessment task/note for context
   * @param {string} atn - The assessment task description
   */
  setAssessmentTask(atn) {
    this.currentATN = atn;
  }

  /**
   * Clear conversation history
   */
  clearConversation() {
    this.conversationHistory = [];
  }

  /**
   * Get the CSRF token from the page
   * @returns {string} CSRF token
   */
  getCSRFToken() {
    return document.querySelector('input[name="_csrf_token"]')?.value || '';
  }

  /**
   * Format sources for display
   * @param {Array} sources - Array of source objects
   * @returns {string} Formatted HTML
   */
  formatSources(sources) {
    if (!sources || sources.length === 0) {
      return '<p>No sources found</p>';
    }

    let html = '<div class="sources"><h4>Sources:</h4><ul>';

    sources.forEach(source => {
      if (source.type === 'file') {
        html += `<li><strong>File:</strong> ${source.filename}</li>`;
      } else if (source.type === 'wikipedia') {
        html += `<li><strong>Wikipedia:</strong> <a href="${source.url}" target="_blank">${source.title}</a></li>`;
      }
    });

    html += '</ul></div>';
    return html;
  }

  /**
   * Format the entire response for display
   * @param {Object} response - Response object from API
   * @returns {string} Formatted HTML
   */
  formatResponse(response) {
    if (!response.status) {
      return `<div class="error">Error: ${response.error}</div>`;
    }

    let html = '<div class="response">';
    html += `<div class="answer">${response.answer || response.response}</div>`;
    
    if (response.sources) {
      html += this.formatSources(response.sources);
    }

    html += '</div>';
    return html;
  }
}

// Initialize globally
const studyHelperAI = new StudyHelperAI();

/**
 * Example usage in HTML
 */

// Single question example
async function exampleQuestion() {
  const prompt = "What is the water cycle?";
  
  console.log('Asking:', prompt);
  const result = await studyHelperAI.askQuestion(prompt, {
    searchWeb: true,
    atn: "Science Chapter 3"
  });

  if (result.status) {
    console.log('Answer:', result.answer);
    console.log('Sources:', result.sources);
    
    // Display in DOM
    document.getElementById('response').innerHTML = 
      studyHelperAI.formatResponse(result);
  } else {
    console.error('Error:', result.error);
  }
}

// Multi-turn conversation example
async function exampleConversation() {
  studyHelperAI.setAssessmentTask("Biology Exam Prep");
  
  // First question
  let result = await studyHelperAI.chat("What is photosynthesis?");
  if (result.status) {
    console.log('AI:', result.response);
  }
  
  // Follow-up question
  result = await studyHelperAI.chat("Can you explain it more simply?");
  if (result.status) {
    console.log('AI:', result.response);
  }
  
  // Another question building on context
  result = await studyHelperAI.chat("How does this relate to cellular respiration?");
  if (result.status) {
    console.log('AI:', result.response);
  }
}

/**
 * HTML Form Example
 * 
 * <form id="promptForm">
 *   <textarea id="promptInput" placeholder="Ask a question..."></textarea>
 *   <label>
 *     <input type="checkbox" id="searchWeb" checked>
 *     Search Wikipedia for additional info
 *   </label>
 *   <button type="submit">Ask AI</button>
 * </form>
 * <div id="response"></div>
 */

document.getElementById('promptForm')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const prompt = document.getElementById('promptInput').value;
  const searchWeb = document.getElementById('searchWeb').checked;
  
  if (!prompt.trim()) return;
  
  // Show loading state
  document.getElementById('response').innerHTML = '<p>Generating answer...</p>';
  
  const result = await studyHelperAI.askQuestion(prompt, { searchWeb });
  
  // Display result
  document.getElementById('response').innerHTML = 
    studyHelperAI.formatResponse(result);
  
  // Clear input
  document.getElementById('promptInput').value = '';
});
