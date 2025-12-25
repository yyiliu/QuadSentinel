# QuadSentinel: Sequential Safety for Machine-Checkable Control in Multi-Agent Systems

This repository contains the implementation of **QuadSentinel**, a four-agent guard system for runtime safety enforcement in multi-agent systems, as described in our paper:

> **QuadSentinel: Sequential Safety for Machine-Checkable Control in Multi-Agent Systems**  
> Yiliu Yang*, Yilei Jiang*, Qunzhong Wang, Yingshui Tan, Xiaoyong Zhu, Sherman S. M. Chow, Bo Zheng, Xiangyu Yue

QuadSentinel compiles natural language safety policies into machine-checkable propositional logic rules and enforces them online through a coordinated team of four specialized agents: State Tracker (PredicateWatcher), Policy Verifier, Threat Watcher, and Referee (JudgeAgent).

## Features

- **Four-agent architecture**: Coordinated guard team for robust safety verification
- **Policy compilation**: Translates natural language policies to executable propositional logic rules
- **Top-k predicate optimization**: Efficient predicate selection using semantic similarity search
- **Hierarchical referee**: Multi-level decision making for conflict resolution
- **Online enforcement**: Real-time monitoring and intervention for actions and messages
- **Stateful monitoring**: Threat level tracking and context-aware policy evaluation

## Project Structure

```
.
├── src/quadsentinel/    # Main QuadSentinel package
│   ├── agent.py         # Core Guard class and create_guard function
│   ├── agents/          # Specialized agent implementations
│   │   ├── judge.py     # Judge agent for action evaluation
│   │   ├── predicate.py # Predicate watcher for policy monitoring
│   │   ├── threat.py    # Threat level assessment
│   │   └── verifier.py  # Policy verification
│   └── utils/           # Utility functions and message handling
└── pyproject.toml       # Package configuration
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yyiliu/QuadSentinel.git
cd QuadSentinel
```

2. Install the package in development mode:
```bash
pip install -e .
```

3. Set up environment variables:
Create a `.env` file in the root directory with:
```
OPENAI_API_KEY=your_api_key_here
```

## Usage

### Basic Setup

```python
from quadsentinel import create_guard

# Create a guard instance
guard = await create_guard()
```

### Adding Policies

```python
# Add main policies from a text file
await guard.add_policy_from_file("path/to/policy.txt")

# (optional) Add message policies for conversation monitoring
await guard.add_message_policy_from_file("path/to/message_policy.txt")
```

### Registering Tools

```python
# Register individual tool
guard.register_tool("tool_name", "Tool description")

# Register multiple tools
guard.register_tools([tool1, tool2, tool3])
```

### Handling Interactions

```python
# Handle text messages (returns tuple of (allowed, reason))
allowed, reason = await guard.handle_message(
    message="interaction message here",
    sender="sender_id", # optional
    recipient="recipient_id" # optional
)

# Handle function calls/actions (returns tuple of (allowed, reason))
allowed, reason = await guard.handle_action(
    action="action_name",
    arguments="action_arguments", # optional
    description="action description", # optional
    sender="sender_id" # optional
)
```

If you use QuadSentinel in your research, please cite:
```bibtex
@article{yang2025quadsentinel,
  author  = {Yang, Yiliu and Jiang, Yilei and Wang, Qunzhong and Tan, Yingshui and Zhu, Xiaoyong and Chow, Sherman S. M. and Zheng, Bo and Yue, Xiangyu},
  title   = {QuadSentinel: Sequent Safety for Machine-Checkable Control in Multi-agent Systems},
  journal = {arXiv preprint arXiv:2512.16279},
  year    = {2025},
  url     = {https://arxiv.org/abs/2512.16279}
}
```
