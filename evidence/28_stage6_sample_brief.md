# Research brief: What are the failure modes of LLM-based multi-agent systems?

## Sub-questions searched

1. What are the common communication failures and coordination breakdowns in LLM-based multi-agent systems?
   - search query: `LLM multi-agent communication failure coordination breakdown`
2. How do cascading errors and hallucination propagation affect the reliability of multi-agent LLM frameworks?
   - search query: `cascading errors hallucination propagation LLM multi-agent reliability`
3. What security vulnerabilities, such as adversarial attacks and prompt injection, emerge in cooperative LLM agents?
   - search query: `security vulnerability adversarial attack prompt injection multi-agent LLM`

## Themes across the evidence

- Vulnerability of LLM multi-agent systems to adversarial attacks and prompt injection
- Propagation and mitigation of errors and hallucinations across collaborative agent frameworks
- The critical role of communication structures and message-based interactions in agent coordination and security
- Graph-based and topological modeling for analyzing, safeguarding, or structuring multi-agent systems

## Gaps this evidence does not address

- Long-term economic or game-theoretic implications of strategic communication failures in large-scale multi-agent deployments
- The specific impact of multi-lingual communication breakdown on cross-organizational and privacy-preserving knowledge exchange
- Empirical analysis of real-world financial or enterprise operational losses resulting from cascading hallucination propagation

## Selected papers (8)

### [0.90] Red-Teaming LLM Multi-Agent Systems via Communication Attacks

**Authors:** Pengfei He, Yuping Lin, Shen Dong, Han Xu, Yue Xing, Hui Liu
**Year:** 2025
**DOI:** 10.48550/arxiv.2502.14847
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 3

**Summary (generated from the abstract):** This paper introduces Agent-in-the-Middle (AiTM), an attack that exploits communication mechanisms in LLM-based multi-agent systems by intercepting and manipulating inter-agent messages. It demonstrates that adversaries can compromise entire systems through message manipulation using an LLM-powered adversarial agent with a reflection mechanism. The work highlights communication frameworks as critical security vulnerabilities in multi-agent systems.

### [0.90] GUARDIAN: Safeguarding LLM Multi-Agent Collaborations with Temporal Graph Modeling

**Authors:** Jialong Zhou, Lichao Wang, Xiao Yang
**Year:** 2025
**DOI:** 10.48550/arxiv.2505.19234
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 2

**Summary (generated from the abstract):** This paper introduces GUARDIAN to address safety challenges such as hallucination amplification and error propagation in multi-agent collaborations. By modeling the collaboration process as a discrete-time temporal attributed graph, the method reconstructs node attributes and graph structures to identify anomalous nodes and edges. It achieves state-of-the-art accuracy in safeguarding multi-agent systems against these safety vulnerabilities.

### [0.90] G-Safeguard: A Topology-Guided Security Lens and Treatment on LLM-based Multi-agent Systems

**Authors:** Shilong Wang, Gui-Min Zhang, Miao Yu, Guancheng Wan, Fanci Meng, Chongye Guo, Kun Wang, Yang Wang
**Year:** 2025
**DOI:** 10.48550/arxiv.2502.11127
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 3

**Summary (generated from the abstract):** This paper presents G-Safeguard, a topology-guided security lens and treatment that uses graph neural networks to detect anomalies on multi-agent utterance graphs and applies topological intervention. It addresses vulnerabilities to adversarial attacks, misinformation propagation, and unintended behaviors. Experiments show it recovers over 40 percent of performance for prompt injection and is adaptable to diverse backbones and large-scale systems.

### [0.90] A Multi-Agent LLM Defense Pipeline Against Prompt Injection Attacks

**Authors:** S. M. Asif Hossain, Ruksat Khan Shayoni, Mohd Ruhul Ameen, Akif Islam, M. Mridha, Jungpil Shin
**Year:** 2025
**DOI:** 10.1109/wiecon-ece69386.2025.11526251
**Verification:** verified against Crossref
**Addresses sub-question(s):** 3

**Summary (generated from the abstract):** This paper presents a multi-agent defense framework employing specialized LLM agents in sequential chain and hierarchical coordinator pipelines to detect and neutralize prompt injection attacks. Evaluated across 55 unique attacks, the multi-agent pipeline achieved complete mitigation by reducing attack success rates to zero. The framework demonstrates robustness across multiple attack categories while maintaining system functionality.

### [0.80] AgentNet: Decentralized Evolutionary Coordination for LLM-based Multi-Agent Systems

**Authors:** Yingxuan Yang, Huacan Chai, Shuai Shao, Yuanyi Song, Siyuan Qi, Renting Rui, Weinan Zhang
**Year:** 2025
**DOI:** 10.48550/arxiv.2504.00587
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1

**Summary (generated from the abstract):** This paper proposes AgentNet, a decentralized, Retrieval-Augmented Generation-based framework that addresses scalability bottlenecks and single points of failure caused by centralized coordination in LLM multi-agent systems. It enables agents to specialize, evolve, and collaborate autonomously in a dynamically structured Directed Acyclic Graph. The framework improves fault tolerance and privacy while achieving higher task accuracy than centralized baselines.

### [0.80] MARCH: Multi-Agent Reinforced Self-Check for LLM Hallucination

**Authors:** Zhuo Li, Yupeng Zhang, Pengyu Cheng, Jiajun Song, Mengyu Zhou, Hao Li, Shujie Hu, Yubin Qin, Erchao Zhao, Xiaoxi Jiang, Guanjun Jiang
**Year:** 2026
**DOI:** 10.48550/arxiv.2603.24579
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 2

**Summary (generated from the abstract):** This paper introduces MARCH to mitigate hallucination bottlenecks in LLM and Retrieval-Augmented Generation systems by overcoming confirmation bias. It orchestrates a collaborative pipeline of a Solver, Proposer, and Checker, utilizing deliberate information asymmetry to validate propositions against retrieved evidence in isolation. Trained with multi-agent reinforcement learning, the framework significantly reduces hallucination rates.

### [0.80] To Protect the LLM Agent Against the Prompt Injection Attack with Polymorphic Prompt

**Authors:** Zhilong Wang, N. Nagaraja, Lan Zhang, Hayretdin Bahşi, Pawan Patil, Peng Liu
**Year:** 2025
**DOI:** 10.1109/dsn-s65789.2025.00037
**Verification:** verified against Crossref
**Addresses sub-question(s):** 3

**Summary (generated from the abstract):** This paper proposes Polymorphic Prompt Assembling, a lightweight defense mechanism protecting LLM agents against prompt injection attacks with near-zero overhead. It addresses the vulnerability where adversarial inputs manipulate model behavior by guessing system prompt structures. By dynamically varying system prompt structures, the approach prevents attackers from predicting the structure to enhance security without compromising performance.

### [0.70] Strategic Communication and Language Bias in Multi-Agent LLM Coordination

**Authors:** Alessio Buscemi, Daniele Proverbio, A. D. Stefano, H. Anh, German Castignani, Pietro Liò
**Year:** 2025
**DOI:** 10.48550/arxiv.2508.00032
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1

**Summary (generated from the abstract):** This paper explores how linguistic framing and strategic communication affect cooperation and coordination in multi-agent LLM scenarios. Using simulated games with models like GPT-4o and Llama 4 Maverick, the study reveals that communication significantly influences agent behavior, though its impact varies by language, personality, and game structure. These findings highlight the dual role of communication in fostering coordination while reinforcing biases.

## Limitations of this search

- Summaries derive from abstracts alone. Full texts were not retrieved, so methods, results and limitations reported only in the body of a paper are not represented here.
- One literature source was searched. Records held only by other indexes will not appear.
- 6 of 8 selected papers could not be independently verified against Crossref. Most are preprints registered with a different agency rather than doubtful records; each paper states its own reason.
