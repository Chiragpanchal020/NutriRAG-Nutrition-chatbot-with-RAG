import { metadata } from "./../../layout";
import { NextRequest } from "next/server";
import OpenAI from "openai";
import { createClient } from "@supabase/supabase-js";

export const config = {
  runtime: "nodejs",
  dynamic: "force-dynamic",
};


const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!,
  { auth: { persistSession: false, autoRefreshToken: false } }
);

// 🪶 Toggle this flag ON during development to see retrieval and answer logs
const DEBUG_MODE = true;

async function embedQuery(query: string) {
  const response = await openai.embeddings.create({
    model: "text-embedding-3-small",
    input: query,
  });
  return response.data[0].embedding;
}

// ... same imports and setup as before

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const message = (body?.message ?? "").toString().trim();

    if (!message) {
      return new Response(JSON.stringify({ error: "Empty Query" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    const queryEmbedding = await embedQuery(message);
    const { data: chunks, error } = await supabase.rpc("match_documents", {
      query_embedding: queryEmbedding,
      match_count: 15,  // Increased from 8 to get more potential matches
      filter: { source: "Human-Nutrition-text.pdf" },
    });

    if (error) throw error;

    const context = chunks
      ?.map(
        (chunk: any, idx: number) =>
          `[${idx + 1}] (Page ${chunk.metadata?.page || "?"}): ${chunk.content}`
      )
      .join("\n\n");

    const userPrompt = `
Use the following context to answer the question accurately.
Cite the page number(s) like [1], [2] and include them at the end of your answer (e.g., p. X).
If the context does not contain the answer, say so.

Context:
${context}

Question: ${message}
`;

    const completion = await openai.chat.completions.create({
      model: "gpt-4o-mini",
      temperature: 0.2,
      messages: [
        {
          role: "system",
          content: `You are a strict RAG assistant. Cite page numbers like [1], [2].`,
        },
        { role: "user", content: userPrompt },
      ],
    });

    const answer =
      completion.choices[0].message?.content?.trim() ??
      "I'm sorry, I couldn't find any relevant information.";

    // ✅ Return both answer and chunk metadata (page + similarity)
    const citations = chunks?.map((chunk: any, idx: number) => ({
      id: idx + 1,
      page: chunk.metadata?.page,
      similarity: chunk.similarity,
      preview: chunk.content.slice(0, 200) + "...",
    }));

    return new Response(JSON.stringify({ answer, citations }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error: any) {
    console.error("❌ Error in /api/chat:", error);
    return new Response(
      JSON.stringify({ error: error.message || "Internal Server Error" }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}
