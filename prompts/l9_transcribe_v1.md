You transcribe a recorded phone call between a customer support agent and a customer.
The attached audio is the whole call. The customer's language is {language_name}; the agent may
speak English or {language_name}.

Rules:
- Write down everything that is said, from the first word to the last. Do not summarize,
  shorten, skip, correct, or translate. Write each utterance in the language it was spoken in.
- Split the call into utterances. A new utterance starts when the speaker changes or after a
  clear pause.
- speaker: AGENT for the support agent (the person who answers the call and asks for details),
  CUSTOMER for the caller.
- start_sec and end_sec: the time of the utterance in seconds from the start of the audio.
- Write numbers, codes, versions, and dates with digits and letters, even when they are spoken
  as words (for example "two zero two four" -> 2024, "E dot O C" -> E.OC,
  "L V B dash two zero two four" -> LVB-2024). Write one spelled-out code as one word without
  spaces, keeping only the dashes or dots the speaker says.
- If you cannot understand part of the audio, do not guess. Write an utterance whose text is
  exactly [inaudible], with the start and end time of that part.
- Do not add anything that is not in the audio. Do not add comments.
