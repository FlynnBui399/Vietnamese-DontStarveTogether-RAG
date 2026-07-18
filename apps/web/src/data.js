export const navigationSections = [
  {
    id: "assistant",
    title: "RAG Assistant",
    links: [
      { label: "Đặt câu hỏi", route: "ask", icon: "◆" },
      { label: "Câu trả lời", route: "answer", icon: "◇" },
      { label: "Nguồn trích dẫn", route: "sources", icon: "◇" },
    ],
  },
  {
    id: "knowledge",
    title: "Knowledge",
    links: [
      { label: "Luồng RAG", route: "pipeline", icon: "✦" },
      { label: "Wiki knowledge", route: "knowledge", icon: "✦" },
      { label: "Auto-ingest", route: "auto-ingest", icon: "✦" },
    ],
  },
  {
    id: "developer",
    title: "Developer",
    links: [
      { label: "System status", route: "system-status", icon: "+" },
      { label: "API documentation", href: "/docs", icon: "+" },
      { label: "OpenAPI schema", href: "/openapi.json", icon: "+" },
    ],
  },
];

export const pageTabs = [
  { id: "ask", label: "Hỏi đáp RAG" },
  { id: "pipeline", label: "Cách hoạt động" },
];

export const suggestedQuestions = [
  { label: "Trang bị", question: "Football Helmet có tác dụng gì?" },
  { label: "Sinh tồn", question: "Làm thế nào để sống sót qua mùa đông?" },
  { label: "Chế tạo", question: "Công thức chế tạo Crock Pot là gì?" },
  { label: "So sánh", question: "So sánh Spear và Hambat." },
];

export const pipelineSteps = [
  {
    id: "query",
    index: "01",
    title: "Vietnamese query",
    shortTitle: "Câu hỏi",
    description: "Nhận câu hỏi tiếng Việt, đồng thời giữ nguyên tên entity tiếng Anh của Don't Starve Together.",
    icon: "?",
  },
  {
    id: "embedding",
    index: "02",
    title: "bge-m3 embedding",
    shortTitle: "Embedding",
    description: "Ollama chuyển câu hỏi thành vector 1024 chiều để tìm kiếm theo ý nghĩa thay vì chỉ khớp từ khóa.",
    icon: "⌁",
  },
  {
    id: "retrieval",
    index: "03",
    title: "Supabase retrieval",
    shortTitle: "Truy xuất",
    description: "Supabase pgvector trả về tối đa năm đoạn Wiki có độ tương đồng vượt ngưỡng evidence.",
    icon: "▤",
  },
  {
    id: "backfill",
    index: "04",
    title: "Wiki auto-ingest",
    shortTitle: "Bổ sung Wiki",
    description: "Nếu kho tri thức chưa có evidence, hệ thống tìm Wiki, ingest trang liên quan rồi truy xuất lại.",
    icon: "↻",
  },
  {
    id: "generation",
    index: "05",
    title: "Grounded answer",
    shortTitle: "Trả lời có nguồn",
    description: "LLM chỉ dựa trên context đã truy xuất để trả lời tiếng Việt và gắn citation [Sx].",
    icon: "✦",
  },
];

export const sourceRules = [
  "Câu trả lời được tạo từ evidence truy xuất trong DST Wiki.",
  "Mỗi ký hiệu [Sx] tương ứng với một nguồn hiển thị bên dưới câu trả lời.",
  "Nguồn luôn giữ tên trang, section và URL gốc từ response /api/chat.",
  "Khi không đủ evidence, trợ lý ưu tiên nói rõ giới hạn thay vì tự bịa dữ kiện.",
];

export const ragData = {
  navigationSections,
  pageTabs,
  suggestedQuestions,
  pipelineSteps,
  sourceRules,
};
