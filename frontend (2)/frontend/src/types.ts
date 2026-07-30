// 错题本相关类型定义
export interface WrongQuestion {
  id: number
  subject: string
  knowledge_point?: string | null
  wrong_reason?: string | null
  wrong_count: number
  status: string
  created_at?: string | null
  question?: Question
}

export interface Question {
  id: number
  question_number: string
  content: string
  student_answer?: string | null
  correct_answer?: string | null
  score?: number | null
  max_score?: number | null
  is_correct?: boolean | null
  explanation?: string | null
  confidence?: number | null
  needs_review?: boolean
  confidence_warning?: string | null
}

// 练习题相关类型
export interface PracticeQuestion {
  id: number
  content: string
  options?: string | null
  correct_answer?: string | null
  explanation?: string | null
  knowledge_point?: string | null
}

export interface PracticeTask {
  id: number
  status: string
  progress: number
  error_message?: string | null
}
