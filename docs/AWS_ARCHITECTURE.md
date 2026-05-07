# AWS System Diagram

This is the high level design for the deployment of the Local agent. 

```mermaid
%% City Agent Pipeline - AWS Architecture
%% Import: draw.io -> Arrange -> Insert -> Advanced -> Mermaid
%% Or paste at https://mermaid.live then export SVG/PNG for Google Drawings
flowchart TD
    EB["EventBridge Scheduler<br/>weekly cron"]
    DL["Dispatcher Lambda<br/>fan-out per city"]

    subgraph VPC["AWS VPC - Public Subnet"]
        ECS["ECS Fargate<br/>1 task per city, parallel"]
        IGW["Internet Gateway"]
        ECS --> IGW
    end

    EXT["External APIs<br/>LLM / scraping"]
    S3[("Amazon S3<br/>report blobs")]
    EML["Email Lambda<br/>format and send"]
    SES["Amazon SES"]
    USERS["User Inboxes"]
    DB[("Supabase Postgres<br/>cities, subscribers, send log")]

    EB --> DL
    DL --> ECS
    IGW --> EXT
    ECS -->|write| S3
    S3 -->|PutObject event| EML
    EML --> SES
    SES --> USERS

    DL -.->|read cities| DB

    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef ext fill:#4A90E2,stroke:#1F3A5F,stroke-width:2px,color:#fff
    classDef db fill:#3ECF8E,stroke:#1F6B47,stroke-width:2px,color:#fff
    classDef store fill:#569A31,stroke:#1F4A14,stroke-width:2px,color:#fff
    classDef user fill:#7B68EE,stroke:#3F2E8C,stroke-width:2px,color:#fff
    class EB,DL,ECS,IGW,EML,SES aws
    class EXT ext
    class DB db
    class S3 store
    class USERS user
    style VPC fill:#E8F4FD,stroke:#1F3A5F,stroke-width:3px,color:#1F3A5F
```
