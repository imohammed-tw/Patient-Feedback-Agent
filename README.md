# Digital Patient Feedback & Experience Agent 

The **NHS Patient Feedback Agent** is a conversational AI system built to collect, analyze, and process patient feedback in real-time via a chatbot interface. It is designed to improve patient engagement and identify service gaps by intelligently interacting with patients, categorizing feedback, and providing structured insight to healthcare administrators.

**Overview:**

● Automates collection of post-visit feedback and satisfaction surveys   
● Implements sentiment analysis on patient reviews and comments   
● Generates trend analysis reports for service quality metrics   
● Identifies recurring issues and improvement opportunities  
● Tracks feedback resolution and follow-up actions   
● Provides real-time alerts for critical patient concerns  

## **Tech Stack**

### **🔧 Backend**

#### **Core Framework**

* **Microsoft AutoGen Core**: Tool-equipped agent architecture  
* **OpenAI GPT-4o-mini**: Language model for conversation generation  
* **FastAPI**: Async web framework for API endpoints  
* **WebSockets**: Real-time bidirectional communication

  #### **Data Layer**

* **MongoDB**: Document-based feedback storage  
* **TextBlob**: Natural language processing for sentiment analysis  
* **Pydantic**: Data validation and serialization

  #### **Observability & Monitoring**

* **OpenTelemetry**: Distributed tracing and metrics collection  
* **AgentOps**: Agent-specific performance monitoring and analytics

### **💻 Frontend**

* React (Vite setup)  
* Tailwind CSS for design  
* WebSocket API for real-time chat

## 📊 Database Collections Overview

**Users\_collection**

| Field | Type | Description |
| :---- | ----- | :---- |
| name | str | Patient's name |
| password | str | Hashed password |
| nhs number | dict | { number, age, gender, treatment, issue } |

**Feedback\_collection**

| Field | Type |
| :---- | ----- |
| patient\_name | str |
| nhs\_number | str |
| satisfaction\_rating | int |
| comments | str |
| category | str |

##  **Key Features**

###  **Intelligent Conversation Management**

* Stateful Multi-Turn Conversations: Maintains context across WebSocket connections  
* Workflow-Driven Interactions: 8-step structured feedback collection process  
* Dynamic Response Generation: Context-aware responses based on sentiment and rating

### **🚨 Critical Issue Detection**

* Real-time Alert System: Detects 24+ critical healthcare keywords  
* Urgent Flag Notifications: Visual alerts for serious concerns  
* Priority Review Queue: Automatic flagging for healthcare team attention

###  **Advanced Analytics**

* Sentiment Analysis: TextBlob-powered emotion detection  
* Automatic Categorization: 7 predefined feedback categories  
* Common Issues Tracking: Trending problem identification  
* Performance Metrics: Response time and token usage monitoring

###  **Comprehensive Observability**

* Dual Tracing Systems: OpenTelemetry \+ AgentOps integration  
* Real-time Monitoring: Console and file-based trace exports  
* Performance Analytics: LLM call metrics, tool execution timing.

**System Architecture Diagram:**

**🔧 Core Components**

### **1\. FeedbackAgent (RoutedAgent)**

The main conversation orchestrator that handles the complete feedback workflow.

```python
class FeedbackAgent(RoutedAgent):
    """Tool-equipped patient feedback agent using RoutedAgent and OpenAIChatCompletionClient."""
    
    @message_handler
    async def handle_feedback_message(self, message: FeedbackMessage, ctx: MessageContext) -> FeedbackMessage:
        # Handles conversation flow with tool execution
        pass  # Your logic here
```


**Key Responsibilities:**

* Maintains conversation state and history  
* Orchestrates tool execution based on workflow steps  
* Integrates with tracing systems for observability  
* Handles error recovery and session resets

### **2\. Tool Execution Layer**

Specialized functions for different aspects of feedback processing.

#### **Core Tools:**

| Tool | Purpose | Input | Output |
| :---- | :---- | :---- | :---- |
| quick\_sentiment\_check | Sentiment analysis | feedback\_text (str) | Sentiment \+ polarity score |
| start\_feedback\_rating\_prompt | Rating request | patient\_name (str) | Standardized rating prompt |
| ask\_for\_feedback\_comments | Detailed feedback | rating (int) | Context-based follow-up question |
| categorize\_feedback | Classification | comments (str) | Category (Staff/Billing/etc.) |
| detect\_critical\_issues | Urgent detection | comments (str) | Critical alert or empty string |
| save\_feedback\_and\_show\_insights | Combined operation | All feedback data | Save confirmation \+ common issues |

#### **Critical Keywords Detection**

The system monitors for 24+ critical healthcare indicators:

```python
critical_keywords = {
    "emergency": "Emergency response concerns",
    "mistake": "Potential medical error", 
    "allergic reaction": "Adverse reaction",
    "neglect": "Patient neglect concern",
    "bleeding": "Excessive bleeding reported",
    # ... 19+ more keywords
}
```


### **3\. Session Management**

Multi-layered session handling for scalable concurrent conversations.

```
UserSession (WebSocket level)
├── FeedbackSession (Agent runtime)
│   ├── SingleThreadedAgentRuntime
│   ├── OpenAIChatCompletionClient
│   └── FeedbackAgent
└── Conversation History & State
```


### **4\. Observability Infrastructure**

#### **OpenTelemetry Integration**

* **Distributed Tracing**: End-to-end request tracking  
* **Custom Metrics**: LLM calls, tool executions, conversation duration  
* **Multiple Exporters**: Console, File, Jaeger (optional), OTLP (optional)

#### **AgentOps Integration**

* **Agent Performance Monitoring**: Specialized metrics for AI agent behavior  
* **Conversation Analytics**: Turn-by-turn interaction analysis  
* **Cost Tracking**: Token usage and API call optimization  
* **Real-time Dashboards**: Visual performance monitoring

![img1](https://github.com/user-attachments/assets/998f07a8-f60e-4b98-8862-c5458023c78c)


#### **File-Based Tracing**

```
logs/
├── traces_YYYYMMDD.log    # Detailed operation logs

```


### **5\. "New Chat" Flow**

* Clears context and agent memory using a `new_chat` message  
* Ensures a fresh conversation every time without confusion

**6\.** **Scheduled Reporting**

*   `APScheduler` to:

  * Send trend analysis daily  
  * Critical Alerts for admins if critical issue keywords spike, implemented through slack app interaction and shortcuts feature.

![img2](https://github.com/user-attachments/assets/5f39c0d8-708c-45d3-840c-2776a481f302)

![img3](https://github.com/user-attachments/assets/a1c50ca6-e9fd-436b-b956-09388eb50732)



