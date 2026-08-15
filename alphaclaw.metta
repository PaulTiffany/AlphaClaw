; AlphaClaw — inference-aware overlay for stock OmegaClaw.
;
; This file intentionally does not replace OmegaClaw's loop, providers, skills,
; memory, or multimodal tooling.  It only makes the resident inference substrate
; explicit to the agent and declares the policy for using multimodal capability
; at the boundary of need.

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

(= (alpha-inference-contract)
   (py-str (
      "ALPHACLAW INFERENCE CONTRACT" (newline)
      "resident_provider: " (provider) (newline)
      "resident_model: " (alpha-resident-model) (newline)
      "resident_modalities: " (alpha-resident-modalities) (newline)
      "multimodal_capability: tool-only" (newline)
      "multimodal_tool: " (alpha-multimodal-tool) (newline)
      "symbolic_target: " (alpha-symbolic-target) (newline)
      "POLICY:" (newline)
      "- Treat resident inference and tool inference as different capabilities." (newline)
      "- Do not claim direct perception of image, audio, video, or other non-text evidence when resident_modalities is text-only." (newline)
      "- On first encounter with a new non-text source, use the configured multimodal capability once to translate/handoff the source into symbolic/text form before substantive reasoning." (newline)
      "- The ingress translation should preserve literal observations, interpretations, uncertainty, unresolved details, and a reference to the original evidence." (newline)
      "- Continue the reasoning trajectory on the symbolic/text representation using resident inference." (newline)
      "- Re-query multimodal capability only when the current symbolic state is insufficient; make the query narrow and evidence-directed." (newline)
      "- Treat multimodal tool output as an observation to reason about, not as infallible ground truth." (newline)
      "- Never infer resident capabilities from the model brand; this contract is the authority for what inference is currently resident.")))

; OmegaClaw's getContext dynamically evaluates prompt-extension entries after
; runtime configuration has been initialized, so provider/model information here
; reflects the actual configured inference path without patching OmegaClaw-Core.
(= (prompt-extension alphaclaw-inference-contract)
   (alpha-inference-contract))
