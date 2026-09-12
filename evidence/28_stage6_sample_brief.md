# Research brief: What are the failure modes of LLM-based multi-agent systems?

## Sub-questions searched

1. What are the common communication and coordination failure modes in LLM-based multi-agent systems?
   - search query: `LLM multi-agent communication failure coordination breakdown`
2. How do error propagation and cascading failures manifest across interacting language model agents?
   - search query: `error propagation cascading failures multi-agent language models`
3. What vulnerabilities lead to alignment drift, hallucination amplification, and task derailment in cooperative LLM agents?
   - search query: `alignment drift hallucination amplification task derailment multi-agent systems`

## Themes across the evidence

- Vulnerabilities and security risks stemming from inter-agent communication and message manipulation
- Cascading error propagation and failures occurring across inter-agent message handoffs and reasoning steps
- Coordination challenges, including centralized bottlenecks and the dual role of communication in fostering cooperation versus reinforcing bias
- Mitigation strategies and architectures designed to improve reliability, such as decentralized frameworks, clarification modules, and iterative refinement mechanisms

## Gaps this evidence does not address

- The long-term evolutionary stability and behavioral drift of multi-agent systems operating autonomously over extended deployment periods
- Quantitative economic or computational cost-benefit trade-offs of deploying complex multi-agent architectures versus simpler baseline models in high-stakes environments

## Selected papers (7)

### [1.00] AgentAsk: Multi-Agent Systems Need to Ask

**Authors:** Bohan Li, Kuo Yang, Ying Lai, Yudong Zhang, C. Zhang, Guibin Zhang, Xinlei Yu, Miao Yu, Xu Wang, Yang Wang
**Year:** 2025
**DOI:** 10.48550/arxiv.2510.07593
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1, 2, 3

**Summary (generated from the abstract):** This work identifies error propagation at inter-agent message handoffs as a primary reason multi-agent systems fail to consistently outperform single-agent baselines. It establishes an edge-level error taxonomy consisting of Data Gap, Signal Corruption, Referential Drift, and Capability Gap. To prevent cascading errors, the authors propose AgentAsk, a lightweight clarification module that applies minimal edge-level interventions.

### [0.90] Red-Teaming LLM Multi-Agent Systems via Communication Attacks

**Authors:** Pengfei He, Yuping Lin, Shen Dong, Han Xu, Yue Xing, Hui Liu
**Year:** 2025
**DOI:** 10.48550/arxiv.2502.14847
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1

**Summary (generated from the abstract):** This paper introduces Agent-in-the-Middle (AiTM), a novel attack that exploits communication mechanisms in LLM-based multi-agent systems by intercepting and manipulating inter-agent messages. It demonstrates that adversaries can compromise entire multi-agent systems solely by altering messages passed between agents using an LLM-powered adversarial agent with a reflection mechanism. The comprehensive evaluation highlights that these systems are vulnerable to communication-based security attacks.

### [0.90] Table-Critic: A Multi-Agent Framework for Collaborative Criticism and Refinement in Table Reasoning

**Authors:** Peiying Yu, Guoxin Chen, Jingjing Wang
**Year:** 2025
**DOI:** 10.48550/arxiv.2502.11799
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 2

**Summary (generated from the abstract):** This paper addresses cascading error propagation during multi-step reasoning processes in table reasoning by introducing Table-Critic, a multi-agent framework for collaborative criticism and iterative refinement. The framework utilizes specialized agents including a Judge, Critic, Refiner, and Curator, supported by a self-evolving template tree to accumulate critique knowledge. Experiments show that this approach achieves superior accuracy and error correction rates.

### [0.80] TEAM-SimHRA: A Team-Based Simulation Framework for Human Reliability Analysis Using Multi-Agent Large Language Models

**Authors:** Xingyu Xiao, Jiejuan Tong, Jingang Liang, Haitao Wang
**Year:** 2026
**DOI:** 10.48550/arxiv.2605.23927
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1, 2

**Summary (generated from the abstract):** This study introduces TEAM-SimHRA to model team-level failures and emergent interaction dynamics in nuclear control rooms using multi-agent large language models. Validated against historical accidents like Three Mile Island and Chernobyl, the framework successfully reproduces collective cognition, role-conditioned authority dynamics, communication suppression, and authority pressure cascades. It demonstrates that multi-agent simulation can extract quantitative reliability indicators for sociotechnical systems.

### [0.70] Strategic Communication and Language Bias in Multi-Agent LLM Coordination

**Authors:** Alessio Buscemi, Daniele Proverbio, A. D. Stefano, H. Anh, German Castignani, Pietro Liò
**Year:** 2025
**DOI:** 10.48550/arxiv.2508.00032
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1

**Summary (generated from the abstract):** This research explores how linguistic framing and strategic communication affect cooperation in LLM-based multi-agent coordination scenarios. Using FAIRGAME simulations with advanced LLMs, the study reveals that communication significantly influences agent behavior and can reinforce existing biases. The findings highlight a dual role for communication in both fostering coordination and propagating language-driven effects.

### [0.70] The Web Tool Trap: Understanding and Mitigating Over-Reliance in LLM Browsing Agents

**Authors:** Jiawei Guo, Hongjie Nie, Qianbo Zang, Shu Yang, Shuodi Liu, Yiwei Ru, Liuyu Xiang, Di Wang, Zhaofeng He
**Year:** 2026
**DOI:** 10.65109/hzer2072
**Verification:** verified against Crossref
**Addresses sub-question(s):** 3

**Summary (generated from the abstract):** This research investigates over-reliance patterns in LLM browsing agents regarding internal knowledge versus external tools through BrowseBench. It identifies three distinct failure modes: excessive conservatism, over-trust in web sources, and planning deficiency. The paper proposes and evaluates mitigations such as Direct Preference Optimization, Attention Refinement, and Hierarchical Query Decomposition.

### [0.60] AgentNet: Decentralized Evolutionary Coordination for LLM-based Multi-Agent Systems

**Authors:** Yingxuan Yang, Huacan Chai, Shuai Shao, Yuanyi Song, Siyuan Qi, Renting Rui, Weinan Zhang
**Year:** 2025
**DOI:** 10.48550/arxiv.2504.00587
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1

**Summary (generated from the abstract):** This paper addresses centralized coordination bottlenecks, scalability limits, and single points of failure in LLM multi-agent systems by proposing AgentNet, a decentralized Retrieval-Augmented Generation-based framework. AgentNet allows agents to specialize, evolve, and collaborate autonomously in a dynamically structured Directed Acyclic Graph. The framework enables fault-tolerant, privacy-preserving collaboration through decentralized coordination, dynamic graph topology, and a retrieval-based memory system.

## Limitations of this search

- Summaries derive from abstracts alone. Full texts were not retrieved, so methods, results and limitations reported only in the body of a paper are not represented here.
- One literature source was searched. Records held only by other indexes will not appear.
- 6 of 7 selected papers could not be independently verified against Crossref. Most are preprints registered with a different agency rather than doubtful records; each paper states its own reason.
