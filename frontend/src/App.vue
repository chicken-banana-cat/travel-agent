<script setup>
import { ref, onMounted, nextTick } from 'vue'
import axios from 'axios'

const messages = ref([])
const userInput = ref('')
const isLoading = ref(false)
const messagesContainer = ref(null)
const sessionId = ref('')  // 세션 ID 저장

// UUID 생성 함수
const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0
    const v = c === 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const sendMessage = async () => {
  if (!userInput.value.trim() || isLoading.value) return

  const userMessage = userInput.value
  messages.value.push({ type: 'user', content: userMessage })
  userInput.value = ''
  await scrollToBottom()

  isLoading.value = true

  try {
    // EventSource를 사용하여 SSE 연결 (세션 ID 포함)
    const eventSource = new EventSource(
      `http://localhost:8000/api/v1/chat?message=${encodeURIComponent(userMessage)}&session_id=${sessionId.value}`
    )

    eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data)
        
        // 에러 처리
        if (parsed.error) {
          messages.value.push({ type: 'error', content: parsed.error })
          scrollToBottom()
          return
        }

        // 중복 메시지 체크를 위한 함수
        const isDuplicateMessage = (content) => {
          if (messages.value.length === 0) return false
          const lastMessage = messages.value[messages.value.length - 1]
          return lastMessage.type === 'bot' && lastMessage.content === content
        }

        // 상태에 따른 처리
        switch (parsed.status) {
          case 'need_more_info':
            // 추가 정보 요청 메시지
            if (!isDuplicateMessage(parsed.message)) {
              messages.value.push({ type: 'bot', content: parsed.message })
            }
            break

          case 'processing':
            // 처리 중 상태 메시지
            if (!isDuplicateMessage(parsed.result)) {
              messages.value.push({ type: 'bot', content: parsed.result })
            }
            break

          case 'success':
            // 최종 결과 메시지
            const successMessage = parsed.result?.message || parsed.message
            if (!isDuplicateMessage(successMessage)) {
              messages.value.push({ type: 'bot', content: successMessage })
            }
            break

          default:
            // 기타 메시지 처리
            const defaultMessage = parsed.message || event.data
            if (!isDuplicateMessage(defaultMessage)) {
              messages.value.push({ type: 'bot', content: defaultMessage })
            }
        }
        scrollToBottom()
      } catch (e) {
        console.error('JSON 파싱 오류:', e, '원본 데이터:', event.data)
        // JSON 파싱 실패 시 일반 텍스트로 처리
        if (!isDuplicateMessage(event.data)) {
          messages.value.push({ type: 'bot', content: event.data })
        }
        scrollToBottom()
      }
    }

    eventSource.onerror = (error) => {
      console.error('EventSource 오류:', error)
      eventSource.close()
      messages.value.push({
        type: 'error',
        content: '메시지 전송 중 오류가 발생했습니다.'
      })
      isLoading.value = false
      scrollToBottom()
    }

    // 에러 이벤트 처리
    eventSource.addEventListener('error', (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.error) {
          const errorMessage = data.stacktrace
            ? `${data.error}\n\nStacktrace:\n${data.stacktrace}`
            : data.error

          messages.value.push({
            type: 'error',
            content: errorMessage
          })
          scrollToBottom()
        }
      } catch (e) {
        console.error('에러 데이터 파싱 실패:', e)
      }
    })

    // 연결이 완료되면 EventSource를 닫음
    eventSource.addEventListener('complete', () => {
      eventSource.close()
      isLoading.value = false
      scrollToBottom()
    })

  } catch (error) {
    console.error('API 요청 오류:', error)
    messages.value.push({
      type: 'error',
      content: '메시지 전송 중 오류가 발생했습니다.'
    })
    isLoading.value = false
    await scrollToBottom()
  }
}

onMounted(() => {
  // 컴포넌트 마운트 시 세션 ID 생성
  sessionId.value = generateUUID()
  
  messages.value.push({ 
    type: 'bot', 
    content: '안녕하세요! 여행 상담사입니다. 어떤 여행을 계획하고 계신가요?' 
  })
})
</script>

<template>
  <div class="chat-container">
    <div class="chat-header">
      <h1>여행 상담사</h1>
    </div>
    <div class="chat-messages" ref="messagesContainer">
      <div v-for="(message, index) in messages" :key="index" 
           :class="['message', message.type]">
        {{ message.content }}
      </div>
    </div>
    <div class="chat-input">
      <input 
        v-model="userInput" 
        @keyup.enter="sendMessage"
        placeholder="여행에 대해 물어보세요..."
        :disabled="isLoading"
      />
      <button @click="sendMessage" :disabled="isLoading">
        {{ isLoading ? '전송 중...' : '전송' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-container {
  max-width: 800px;
  margin: 0 auto;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f5f5f5;
}

.chat-header {
  background-color: #4CAF50;
  color: white;
  padding: 1rem;
  text-align: center;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.message {
  max-width: 70%;
  padding: 0.8rem;
  border-radius: 1rem;
  word-wrap: break-word;
}

.user {
  align-self: flex-end;
  background-color: #4CAF50;
  color: white;
}

.bot {
  align-self: flex-start;
  background-color: white;
  color: #333;
}

.error {
  align-self: center;
  background-color: #ffebee;
  color: #c62828;
}

.chat-input {
  padding: 1rem;
  background-color: white;
  display: flex;
  gap: 0.5rem;
  border-top: 1px solid #ddd;
}

input {
  flex: 1;
  padding: 0.8rem;
  border: 1px solid #ddd;
  border-radius: 0.5rem;
  font-size: 1rem;
}

button {
  padding: 0.8rem 1.5rem;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 0.5rem;
  cursor: pointer;
  font-size: 1rem;
}

button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}

button:hover:not(:disabled) {
  background-color: #45a049;
}
</style>
