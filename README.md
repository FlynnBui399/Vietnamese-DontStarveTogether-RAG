# DST Wiki Chatbot — MVP

Đường chạy mặc định của project chỉ còn bốn bước:

```text
Wiki → bge-m3 → Supabase pgvector → DeepSeek → câu trả lời có nguồn
```

Các module ingestion/retrieval/evaluation nâng cao cũ vẫn được giữ để tham khảo,
nhưng API MVP không import hoặc phụ thuộc vào chúng.
Migration cũ nằm trong `supabase/legacy_migrations`; Supabase mặc định chỉ áp
dụng migration một bảng của MVP.

## 1. Cài đặt

```powershell
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
ollama pull bge-m3
```

Điền `SUPABASE_URL`, `SUPABASE_SECRET_KEY` và `DEEPSEEK_API_KEY` trong `.env`.
Sau đó áp dụng migration Supabase:

```powershell
supabase db push
```

Máy chưa có Supabase CLI có thể mở SQL Editor trên Supabase Dashboard và chạy
file `supabase/migrations/20260717000000_mvp_wiki_chunks.sql`.

## 2. Ingest các trang cần dùng

Chỉ ingest các trang thực sự cần cho chatbot nhỏ:

```powershell
python -m scripts.ingest_mvp "Wilson" "Football Helmet" "Seasons"
```

Chạy lại lệnh với cùng tiêu đề sẽ thay thế các chunk cũ của trang đó.

API cũng có auto-ingest mặc định. Khi `/api/chat` không tìm thấy evidence trong
Supabase, nó sẽ search Wiki theo câu hỏi, ingest tối đa `AUTO_INGEST_MAX_PAGES`
trang liên quan, rồi retry retrieval. Ingest thủ công vẫn hữu ích cho các topic
quan trọng cần phản hồi nhanh và ổn định.

## 3. Chạy API

```powershell
python -m uvicorn apps.api.main:app --reload
```

Kiểm tra:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/chat `
  -ContentType "application/json" `
  -Body '{"message":"Football Helmet có tác dụng gì?"}'
```

Response `/api/chat` chỉ có hai trường:

```json
{
  "answer": "... [S1]",
  "sources": [{"title": "...", "section": "...", "url": "..."}]
}
```

## Phạm vi MVP

- Có: làm sạch Wiki, chunking, embedding, vector top-k, DeepSeek và citation.
- Chưa dùng: alias expansion, full-text search, RRF, reranker, corpus lifecycle,
  snapshot/rollback và release evaluation.
