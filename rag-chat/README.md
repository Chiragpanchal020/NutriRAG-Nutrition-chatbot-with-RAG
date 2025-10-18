# RAG Chat Frontend

This is the Next.js frontend for the NutriRAG Nutrition Chatbot. It provides a user-friendly chat interface for interacting with the RAG backend.

## Architecture

The following diagram illustrates the architecture of the NutriRAG chatbot:

![Architecture Diagram](./assets/architecture.svg)

## Tech Stack

-   [Next.js](https://nextjs.org/) - React framework for building user interfaces.
-   [React](https://reactjs.org/) - A JavaScript library for building user interfaces.
-   [Tailwind CSS](https://tailwindcss.com/) - A utility-first CSS framework for rapid UI development.
-   [TypeScript](https://www.typescriptlang.org/) - A typed superset of JavaScript that compiles to plain JavaScript.

## Getting Started

### Prerequisites

-   Node.js and npm
-   An OpenAI API key
-   A Supabase account

### Installation

1.  **Navigate to the `rag-chat` directory:**
    ```bash
    cd rag-chat
    ```
2.  **Install dependencies:**
    ```bash
    npm install
    ```
3.  **Set up environment variables:**
    Create a `.env.local` file in this directory and add your OpenAI and Supabase credentials. The backend API route will use these to connect to the services.
    ```env
    OPENAI_API_KEY="your-openai-api-key"
    SUPABASE_URL="your-supabase-url"
    SUPABASE_SERVICE_ROLE_KEY="your-supabase-service-role-key"
    ```
4.  **Run the development server:**
    ```bash
    npm run dev
    ```
5.  Open [http://localhost:3000](http://localhost:3000) in your browser to see the application.

## API Route

The frontend communicates with a backend API route located at `src/app/api/chat/route.ts`. This route handles the logic for:
1.  Receiving the user's message.
2.  Generating an embedding for the message using OpenAI.
3.  Querying the Supabase vector store to find relevant documents.
4.  Sending the retrieved documents and the original question to an OpenAI model to generate a final answer.
5.  Returning the answer and citations to the frontend.
