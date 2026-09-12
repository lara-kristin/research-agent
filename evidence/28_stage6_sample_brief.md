# Research brief: What are the failure modes of LLM-based multi-agent systems?

## Sub-questions searched

1. What are the common communication breakdown and coordination failure modes in LLM-based multi-agent systems?
   - search query: `llm multi agent communication failure coordination breakdown`
2. How do error propagation and cascading failure mechanisms affect the reliability of collaborative large language model agents?
   - search query: `error propagation cascading failures llm multi agent reliability`
3. What are the security vulnerabilities, emergent malicious behaviors, and alignment failures observed in multi-agent LLM frameworks?
   - search query: `security vulnerabilities emergent malicious behavior alignment failures llm agents`

## Themes across the evidence

- Vulnerability of LLM-based multi-agent and GUI systems to communication attacks, prompt injections, and stealthy malicious behaviors
- Challenges in system-level reliability, failure localization, and error attribution across multi-step interaction trajectories
- Trade-offs and failures associated with current safety defenses, including defense training breaking agent competence and inducing cascading failures
- Coordination structures and communication frameworks impacting agent cooperation, scalability, and bias

## Gaps this evidence does not address

- Long-term economic or multi-organizational adoption barriers beyond basic privacy and proprietary knowledge concerns
- The direct measurement of human psychological or behavioral adaptation over extended periods of interacting with vulnerable GUI agents

## Selected papers (8)

### [1.00] When Agents Go Rogue: Activation-Based Detection of Malicious Behaviors in Multi-Agent Systems

**Authors:** Haowen Xu, Xue Tan, Lei Ma, Zhihao Zhang, Chao Wang, Qingze Wang, Ping Chen, Jun Dai, Xiaoyan Sun
**Year:** 2026
**DOI:** 10.48550/arxiv.2607.06807
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1, 3

**Summary (generated from the abstract):** This work proposes AcMAS, an activation-based framework that detects stealthy malicious behaviors in multi-agent systems by analyzing internal reasoning states in the activation space of local agents. AcMAS operates without relying on explicit interaction graphs and provides critical signals to restore the functionality of compromised agents rather than isolating them.

### [0.90] Red-Teaming LLM Multi-Agent Systems via Communication Attacks

**Authors:** Pengfei He, Yuping Lin, Shen Dong, Han Xu, Yue Xing, Hui Liu
**Year:** 2025
**DOI:** 10.48550/arxiv.2502.14847
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1, 3

**Summary (generated from the abstract):** This paper introduces Agent-in-the-Middle (AiTM), a novel attack that exploits communication mechanisms in LLM-based multi-agent systems by intercepting and manipulating inter-agent messages. It demonstrates that adversaries can compromise entire systems with limited control by utilizing an LLM-powered adversarial agent with a reflection mechanism to generate malicious instructions.

### [0.90] The Autonomy Tax: Defense Training Breaks LLM Agents

**Authors:** Li Li, Yue Zhao
**Year:** 2026
**DOI:** 10.48550/arxiv.2603.19423
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1, 2, 3

**Summary (generated from the abstract):** The paper investigates the capability-alignment paradox where defense training intended to protect LLM agents against prompt injection systematically harms agent competence. Evaluating defended models across multi-step tasks uncovers three systematic biases: agent incompetence bias, cascade amplification bias where early failures propagate through retry loops, and trigger bias.

### [0.80] Strategic Communication and Language Bias in Multi-Agent LLM Coordination

**Authors:** Alessio Buscemi, Daniele Proverbio, A. D. Stefano, H. Anh, German Castignani, Pietro Liò
**Year:** 2025
**DOI:** 10.48550/arxiv.2508.00032
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1

**Summary (generated from the abstract):** The paper explores how linguistic framing and strategic communication affect cooperation in multi-agent LLM scenarios using FAIRGAME simulations with models like GPT-4o and Llama 4 Maverick. The findings reveal that communication significantly influences agent behavior, acting in a dual role to both foster coordination and reinforce language-driven biases.

### [0.80] VerifyMAS: Hypothesis Verification for Failure Attribution in LLM Multi-Agent Systems

**Authors:** Hezhe Qiao, Hanghang Tong, Ee-Peng Lim, Bing Liu, Guansong Pang
**Year:** 2026
**DOI:** 10.48550/arxiv.2605.17467
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1

**Summary (generated from the abstract):** The paper proposes VerifyMAS, a hypothesis verification framework designed to automatically attribute failures in multi-agent systems by verifying hypotheses against full interaction trajectories. This error-first approach captures global failure patterns such as cross-step inconsistencies and coordination errors while reducing the combinatorial search space for agent localization.

### [0.80] The Obvious Invisible Threat: LLM-Powered GUI Agents' Vulnerability to Fine-Print Injections

**Authors:** Chaoran Chen, Zhiping Zhang, Bingcan Guo, Shang Ma, Ibrahim Khalilov, S. Gebreegziabher, Yanfang Ye, Ziang Xiao, Yaxing Yao, Tian-Shi Li, Toby Jia-Jun Li
**Year:** 2025
**DOI:** 10.48550/arxiv.2504.11281
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 3

**Summary (generated from the abstract):** This paper characterizes six types of attacks where adversaries inject malicious content into GUIs to alter agent behaviors or induce unintended disclosures of private information. An experimental study with state-of-the-art GUI agents and adversarial webpages shows high vulnerability to contextually embedded threats and highlights the insufficiency of simple human oversight.

### [0.70] AgentNet: Decentralized Evolutionary Coordination for LLM-based Multi-Agent Systems

**Authors:** Yingxuan Yang, Huacan Chai, Shuai Shao, Yuanyi Song, Siyuan Qi, Renting Rui, Weinan Zhang
**Year:** 2025
**DOI:** 10.48550/arxiv.2504.00587
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1

**Summary (generated from the abstract):** This work proposes AgentNet, a decentralized, RAG-based framework allowing LLM-based agents to autonomously specialize, evolve, and collaborate in a dynamically structured Directed Acyclic Graph. By eliminating central orchestration and using a retrieval-based memory system, it addresses scalability bottlenecks, privacy concerns, and single points of failure while achieving higher task accuracy.

### [0.70] DoVer: Intervention-Driven Auto Debugging for LLM Multi-Agent Systems

**Authors:** Ming-Jie Ma, Jue Zhang, Fangkai Yang, Yu Kang, Qingwei Lin, S. Rajmohan, Dongmei Zhang
**Year:** 2025
**DOI:** 10.48550/arxiv.2512.06749
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1

**Summary (generated from the abstract):** This study introduces DoVer, an intervention-driven debugging framework that tackles the limits of log-only debugging by pairing hypothesis generation with active verification through targeted interventions. Evaluated on outcome-oriented task success across multiple frameworks and datasets, DoVer recovers failed trials and validates or refutes failure hypotheses.

## Limitations of this search

- Summaries derive from abstracts alone. Full texts were not retrieved, so methods, results and limitations reported only in the body of a paper are not represented here.
- One literature source was searched. Records held only by other indexes will not appear.
- 8 of 8 selected papers could not be independently verified against Crossref, of which 8 are preprints registered with a different agency rather than doubtful records. Each paper states its own reason.
