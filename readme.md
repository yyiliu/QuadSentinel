# Guard

Guard is a sophisticated AI safety and policy enforcement system designed to monitor and control AI agent interactions, particularly focusing on preventing harmful or inappropriate behaviors in AI systems.

## Project Structure

```
.
├── src/guard/           # Main Guard package
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
git clone [repository-url]
cd Guard
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
from guard import create_guard

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