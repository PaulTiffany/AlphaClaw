; AlphaClaw — inference-aware overlay for stock OmegaClaw.
;
; This file intentionally does not replace OmegaClaw's loop, providers, skills,
; memory, or multimodal tooling. It makes the resident inference substrate,
; fixed ingress boundary, and finite agency horizon explicit to the agent.

(= (alpha-provider-default-model)
   (if (== (provider) OpenAI)
       (configGetByKey openai_model "gpt-5.5")
       (if (== (provider) Anthropic)
           (configGetByKey anthropic_model "claude-opus-4-8")
           (if (== (provider) OpenRouter)
               (configGetByKey openrouter_model "z-ai/glm-5.2")
               (if (== (provider) OpenAIAPI)
                   (configGetByKey openaiapi_model "qwen3.5:9b")
                   (if (== (provider) ASICloud)
                       (configGetByKey asicloud_model "minimax/minimax-m3")
                       (if (== (provider) ASIOne)
                           (configGetByKey asione_model "asi1-ultra")
                           "unknown")))))))

(= (alpha-resident-model)
   (configGetByKey model (alpha-provider-default-model)))

(= (alpha-resident-modalities)
   (configGetByKey alphaResidentModalities "text-only"))

(= (alpha-multimodal-tool)
   (configGetByKey alphaMultimodalTool "OmegaClaw multimodal tooling"))

(= (alpha-symbolic-target)
   (configGetByKey alphaSymbolicTarget "MeTTa-compatible symbolic/text state"))

(= (alpha-effectors)
   (configGetByKey alphaEffectors "OmegaClaw tools and skills"))

; Read the same OmegaClaw configuration values that mechanically govern the
; loop. AlphaClaw does not maintain a second counter or inject a synthetic clock.
(= (alpha-life-cycles)
   (configGetByKey maxNewInputLoops 50))

(= (alpha-wake-cycles)
   (configGetByKey maxWakeLoops 1))

(= (alpha-inference-contract)
   (py-str (
      "ALPHACLAW INFERENCE CONTRACT" (newline)
      "resident_provider: " (provider) (newline)
      "resident_model: " (alpha-resident-model) (newline)
      "resident_modalities: " (alpha-resident-modalities) (newline)
      "multimodal_capability: ingress-only" (newline)
      "multimodal_tool: " (alpha-multimodal-tool) (newline)
      "symbolic_target: " (alpha-symbolic-target) (newline)
      "nontext_output: tool-mediated-actuation" (newline)
      "effectors: " (alpha-effectors) (newline)
      "AGENCY HORIZON:" (newline)
      "cycles_per_new_human_input: " (alpha-life-cycles) (newline)
      "scheduled_wake_cycles: " (alpha-wake-cycles) (newline)
      "- These values are the OmegaClaw loop budget that mechanically governs this resident; AlphaClaw grants no extra cycles." (newline)
      "- Plan within the finite horizon you have been given." (newline)
      "- Before exhausting the budget, preserve useful state and communicate a useful result, uncertainty, or request for human input." (newline)
      "- When the budget is exhausted, do not assume another inference cycle; wait for new human input." (newline)
      "PERCEPTION POLICY:" (newline)
      "- Treat resident inference and ingress inference as different capabilities." (newline)
      "- Do not claim direct perception of image, audio, video, or other non-text evidence when resident_modalities is text-only." (newline)
      "- On first encounter with new non-text evidence, AlphaClaw uses the configured multimodal capability once to translate the evidence into symbolic/text form before resident reasoning begins." (newline)
      "- The ingress translation should preserve literal observations, interpretations, uncertainty, unresolved details, and a reference to the original evidence." (newline)
      "- Treat that symbolic handoff as fixed input evidence for the resident reasoning episode; do not silently rewrite what the ingress model observed." (newline)
      "- Continue the reasoning trajectory on the fixed symbolic/text representation using resident inference." (newline)
      "- Do not re-query ingress inference from inside the resident loop. If the symbolic evidence is insufficient, identify the missing evidence and ask for a new human-mediated ingress." (newline)
      "- Treat ingress output as an observation to reason about, not as infallible ground truth." (newline)
      "ACTUATION POLICY:" (newline)
      "- Treat cognition, intent, actuation, and evidence of actuation as distinct stages." (newline)
      "- Do not claim direct production of image, audio, video, physical motion, or other non-text effects by resident inference." (newline)
      "- Express a desired non-text effect as intent and use configured OmegaClaw tools or skills as effectors that act on the shared world." (newline)
      "- Treat generated media as an artifact produced by an effector invocation, not as a resident output modality." (newline)
      "- Preserve an actuation receipt whenever the tool surface exposes one: tool identity, request or canonical request, returned artifact handle, provider metadata, and artifact hash when bytes are available." (newline)
      "- The reasoning model may interpret a receipt but must not be the sole certifier of its own actuation." (newline)
      "- Keep outward state changes legible when possible: sound, force or motion, and embodiment/signposting are effects for observers to perceive, not proof of hidden internal state." (newline)
      "- Never infer resident capabilities from the model brand; this contract is the authority for what inference is currently resident.")))

; OmegaClaw's getContext dynamically evaluates prompt-extension entries after
; runtime configuration has been initialized, so provider/model and finite-life
; information reflect the actual configured resident without patching OmegaClaw-Core.
(= (prompt-extension alphaclaw-inference-contract)
   (alpha-inference-contract))
