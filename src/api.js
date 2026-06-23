const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const getAuthToken = () => {
return localStorage.getItem('access_token')
}

export const setAuthToken = (token) => {
localStorage.setItem('access_token', token)
}

export const clearAuthToken = () => {
localStorage.removeItem('access_token')
}

export const getAuthHeaders = () => {
const token = getAuthToken()
return token ? { Authorization: `Bearer ${token}` } : {}
}

async function parseErrorResponse(response) {
const contentType = response.headers.get('content-type') || ''

try {
if (contentType.includes('application/json')) {
return await response.json()
}

```
const text = await response.text()
return { detail: text || response.statusText }
```

} catch {
return { detail: response.statusText }
}
}

function getErrorMessage(errorBody, fallbackMessage) {
if (!errorBody) {
return fallbackMessage
}

if (typeof errorBody.detail === 'string') {
return errorBody.detail
}

if (Array.isArray(errorBody.detail)) {
return JSON.stringify(errorBody.detail, null, 2)
}

if (errorBody.detail && typeof errorBody.detail === 'object') {
return JSON.stringify(errorBody.detail, null, 2)
}

if (typeof errorBody.message === 'string') {
return errorBody.message
}

return JSON.stringify(errorBody, null, 2) || fallbackMessage
}

export async function signup(payload) {
const response = await fetch(`${API_BASE_URL}/api/v1/auth/signup`, {
method: 'POST',
headers: {
'Content-Type': 'application/json',
},
body: JSON.stringify(payload),
})

if (!response.ok) {
const errorBody = await parseErrorResponse(response)
throw new Error(getErrorMessage(errorBody, '회원가입에 실패했습니다.'))
}

return response.json()
}

export async function login(payload) {
const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
method: 'POST',
headers: {
'Content-Type': 'application/json',
},
body: JSON.stringify(payload),
})

if (!response.ok) {
const errorBody = await parseErrorResponse(response)
throw new Error(getErrorMessage(errorBody, '로그인에 실패했습니다.'))
}

return response.json()
}

export async function authFetch(path, options = {}) {
const headers = {
'Content-Type': 'application/json',
...getAuthHeaders(),
...options.headers,
}

const response = await fetch(`${API_BASE_URL}${path}`, {
...options,
headers,
})

if (!response.ok) {
const errorBody = await parseErrorResponse(response)
throw new Error(getErrorMessage(errorBody, '요청에 실패했습니다.'))
}

return response.json()
}