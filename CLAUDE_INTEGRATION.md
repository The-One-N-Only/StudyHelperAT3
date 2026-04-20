# Claude AI Integration Guide for StudyHelperAT3

## Overview
Your StudyHelperAT3 app now has AI-powered prompt answering that intelligently searches through your uploaded files and whitelisted websites to answer questions.

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

This installs the `anthropic` SDK needed for Claude API calls.

### 2. Set Your API Key
Add your Claude API key to your `.env` file:
```
ANTHROPIC_API_KEY=sk-ant-...your-key-here...
```

Get your key from: https://console.anthropic.com/account/keys

### 3. Start the App
```bash
python app.py
```

## Features

### 1. **Upload Files First**
- The system searches through PDFs, DOCX, and TXT files you upload
- It indexes the text and uses keyword matching to find relevant information
- More files = better context for answers

### 2. **Answer a Question**
The system will:
- Search your uploaded files for relevant information
- Optionally search Wikipedia for additional context
- Use Claude to synthesize an answer based on all available information
- Return sources for proper attribution

### 3. **Multi-turn Conversations**
Have back-and-forth conversations where Claude remembers context from your files.

## API Reference

### `/api/answer/prompt` (POST)
Single-turn question answering.

**Request:**
```json
{
  "prompt": "What is photosynthesis?",
  "search_web": true,
  "atn": "Biology Chapter 3"
}
```

**Response:**
```json
{
  "status": true,
  "answer": "Photosynthesis is the process...",
  "sources": [
    {
      "type": "file",
      "filename": "biology_textbook.pdf",
      "file_id": 1
    },
    {
      "type": "wikipedia",
      "title": "Photosynthesis",
      "url": "https://en.wikipedia.org/wiki/Photosynthesis"
    }
  ]
}
```

### `/api/answer/chat` (POST)
Multi-turn conversation with memory.

**Request:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "What causes climate change?"
    },
    {
      "role": "assistant",
      "content": "Climate change is primarily caused by..."
    },
    {
      "role": "user",
      "content": "What can we do about it?"
    }
  ],
  "atn": "Environmental Science"
}
```

**Response:**
```json
{
  "status": true,
  "response": "There are many actions we can take...",
  "sources": [...]
}
```

## How It Works

1. **File Indexing**: When you upload files, text is extracted and stored
2. **Context Retrieval**: For each question:
   - Keywords from the prompt are searched across all files
   - Relevant passages are extracted
   - Optional Wikipedia search adds additional information
3. **Claude Processing**: All context is sent to Claude with the question
4. **Answer Generation**: Claude synthesizes a comprehensive answer
5. **Source Attribution**: The response includes where information came from

## Security Features

- ✅ Only whitelisted websites are searched (Wikipedia, scholars, academic sources)
- ✅ Your files stay secure in the database
- ✅ API key remains private in `.env`
- ✅ User authentication required

## Whitelisted Sources

The system can safely search:
- Wikipedia
- Google Scholar
- PubMed
- JSTOR
- Springer
- BBC, National Geographic
- University (.edu, .edu.au, .ac.uk) and government (.gov.au) sites
- Academic repositories

## Tips for Best Results

1. **Upload Relevant Files**: The more context, the better the answers
2. **Be Specific**: More specific prompts get more relevant answers
3. **Use Assessment Tasks**: The `atn` parameter helps Claude understand your assignment requirements
4. **Check Sources**: Always verify sources provided in the response
5. **Multi-turn Conversations**: Reference previous questions for better context

## Error Handling

The API returns clear error messages:
- "Not logged in" - User session expired
- "No prompt provided" - Empty question
- "Failed to generate answer" - Claude API issue

## Example Usage in Frontend

```javascript
// Single question
async function askQuestion(prompt) {
  const response = await fetch('/api/answer/prompt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: prompt,
      search_web: true,
      atn: "Assignment Context"
    })
  });
  return await response.json();
}

// Multi-turn chat
async function continueChat(messages) {
  const response = await fetch('/api/answer/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: messages,
      atn: "Assignment Context"
    })
  });
  return await response.json();
}
```

## Limitations

- Max context: ~4000 characters from files, ~2000 from Wikipedia
- Response limit: 2048 tokens (Claude's limit)
- File size: Depends on text extraction capability
- Rate limits: Depends on Claude API plan

## Support

If you encounter issues:
1. Check your API key is valid
2. Ensure files have been uploaded and contain extractable text
3. Check the `user_activity.log` for error details
4. Verify your internet connection for web searches

Enjoy your AI-powered study helper! 📚
