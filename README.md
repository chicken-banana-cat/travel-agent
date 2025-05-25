# Travel Agent

## Agent 구조
```mermaid
graph TD
    User[사용자 입력] --> Planner[Planner Agent]
    User --> Rec[Recommendation Agent]
    Rec --> Planner
    Planner --> Calendar[Calendar Agent]
    Planner --> Celery[Celery]
    Celery --> Search[Search Agent]
    Celery --> Mail[Mail Agent]
```

## Infra Architecture
```mermaid
graph TD
    CF[CloudFront<br/>S3 + Vue] --> API[AWS App Runner<br/>FastAPI]
    API --> DynamoDB[(DynamoDB)]
    API --> SQS[SQS Queue]
    SQS --> Lambda[Lambda<br/>Celery]
```
- Vue로 정말 간단한 프론트를 빌드해 S3에 올려 CloudFront로 배포하였습니다.
- StreamResponse를 위해 AWS App Runner로 FastAPI를 배포하였습니다.
- 각종 context 저장을 위해 DynamoDB를 이용하였습니다.
- Search Agent가 naver API ratelimit 등 오래 걸려, 비동기 처리하였고 Celery Broker로 SQS를 이용하였습니다.
- Celery Worker로 Lambda를 이용하였습니다.
- 각 배포는 deploy.sh frontend/deploy.sh setup_lambda.sh 를 통해 할 수 있습니다.
- [주소](https://dm7qnuxu8ey5m.cloudfront.net)


## 개선할 점
- 다양한 LLM 모델들의 ModelConfig가 부족합니다.
- Agent Response Json 정규화가 많이 되지 않았습니다.
- 캘린더 등록 시 LLM을 이용한 작업이기보다는, 분기를 통한 작업으로 두었습니다.
- UI/UX적으로 부족합니다.
- email 전송 이후 Flow가 좀 어색합니다.
- pre-commit / github action 등 개발 편의, 협업 도구가 부족합니다.
- test code가 부족합니다.

## 시연 스크린샷
<img width="756" alt="image" src="https://github.com/user-attachments/assets/387d5ba7-e6c2-47d0-83f1-d34d58823d90" />
<img width="764" alt="image" src="https://github.com/user-attachments/assets/8b2088c1-39d6-4369-85e1-21f3c3d8a377" />
<img width="766" alt="image" src="https://github.com/user-attachments/assets/16ba461f-161f-44a0-90f7-82334b25d833" />
<img width="779" alt="image" src="https://github.com/user-attachments/assets/8fceef7d-d3d3-4ddd-99c1-601628742740" />
<img width="774" alt="image" src="https://github.com/user-attachments/assets/d8f7599d-10ab-4d71-bb2c-71fe827e761a" />
<img width="755" alt="image" src="https://github.com/user-attachments/assets/8610ed4e-3a20-4f65-a699-900a0afe4ec1" />
<img width="776" alt="image" src="https://github.com/user-attachments/assets/776ebdcb-94d1-4eb2-8e25-fc0017eb036d" />
<img width="789" alt="image" src="https://github.com/user-attachments/assets/8f6d8384-d59d-40b4-bfd9-fe96efe909c5" />
<img width="927" alt="image" src="https://github.com/user-attachments/assets/cd6cecf6-2409-49ad-94ec-edada93ce66a" />
<img width="1839" alt="image" src="https://github.com/user-attachments/assets/07959925-414b-4a57-8c61-d339850b233c" />
<img width="1901" alt="image" src="https://github.com/user-attachments/assets/dc36b053-9f4e-490a-9585-c0cfd3d466da" />
<img width="1872" alt="image" src="https://github.com/user-attachments/assets/f4b7e687-4991-4b98-b695-48e05df053b6" />
<img width="1819" alt="image" src="https://github.com/user-attachments/assets/69653b32-f427-4dc2-ac6e-46cace7089f3" />
<img width="1858" alt="image" src="https://github.com/user-attachments/assets/c468e1eb-f3ad-46b9-a282-7bd461abd720" />










