-- FILE: init.sql

BEGIN;

-- Kích hoạt các extension cần thiết
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

-- Dọn dẹp các bảng cũ
DROP TABLE IF EXISTS public.chat_histories CASCADE;
DROP TABLE IF EXISTS public.insurance_products CASCADE;
DROP TABLE IF EXISTS public.order_list CASCADE;
DROP TABLE IF EXISTS public.orders CASCADE;
DROP TABLE IF EXISTS public.infor_user CASCADE;

-- Bảng lưu trữ lịch sử chat đầy đủ
CREATE TABLE public.chat_histories (
    id          BIGSERIAL PRIMARY KEY,
    is_bot      BOOLEAN NOT NULL DEFAULT FALSE,
    d_name      TEXT,
    message_id  TEXT NOT NULL UNIQUE,
    text        TEXT,
    from_id     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Bảng lưu thông tin người dùng và thống kê
CREATE TABLE public.infor_user (
    id                  BIGSERIAL PRIMARY KEY,
    from_id             TEXT NOT NULL UNIQUE,
    user_name           TEXT,
    user_email          TEXT,
    user_phone          TEXT,
    status              TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'middle', 'vip')),
    qty_insurance       INTEGER NOT NULL DEFAULT 0,
    last_buy            BIGINT,
    total_buy           NUMERIC(20,2) NOT NULL DEFAULT 0 CHECK (total_buy >= 0),
    preferred_language  TEXT NOT NULL DEFAULT 'vi' CHECK (preferred_language IN ('vi', 'en', 'zh')),
    language_detected_at TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Bảng danh mục sản phẩm bảo hiểm
CREATE TABLE public.insurance_products (
    insurance_id    BIGSERIAL PRIMARY KEY,
    insurance_name  TEXT NOT NULL,
    insurance_type  TEXT NOT NULL,
    sum_insured     NUMERIC(20,2) NOT NULL,
    term            TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Bảng tổng hợp giỏ hàng (một giỏ hàng cho mỗi người dùng ở trạng thái pending)
CREATE TABLE public.order_list (
    id            BIGSERIAL PRIMARY KEY,
    from_id       TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    total_count   INTEGER NOT NULL DEFAULT 1,
    total_amount  NUMERIC(20,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    qr_payment    TEXT,
    note          TEXT DEFAULT 'CHUYEN KHOAN MUA BAO HIEM CONG TY EKKO',
    human_check   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Bảng chi tiết các sản phẩm trong một giỏ hàng
CREATE TABLE public.orders (
    id             BIGSERIAL PRIMARY KEY,
    order_list_id  BIGINT,
    insurance_id   BIGINT NOT NULL REFERENCES public.insurance_products(insurance_id),
    qty            INTEGER NOT NULL DEFAULT 1 CHECK (qty > 0),
    amount         NUMERIC(20,2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
    from_id        TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Thêm các ràng buộc Foreign Key
ALTER TABLE public.order_list ADD CONSTRAINT fk_order_list_from_id FOREIGN KEY (from_id) REFERENCES public.infor_user(from_id);
ALTER TABLE public.orders ADD CONSTRAINT fk_orders_order_list_id FOREIGN KEY (order_list_id) REFERENCES public.order_list(id) ON DELETE CASCADE;


-- FUNCTIONS AND TRIGGERS

CREATE OR REPLACE FUNCTION update_order_totals()
RETURNS TRIGGER AS $$
DECLARE
    v_count  INTEGER;
    v_amount NUMERIC(20,2);
    v_order_list_id BIGINT;
BEGIN
    v_order_list_id := COALESCE(NEW.order_list_id, OLD.order_list_id);
    
    SELECT COALESCE(SUM(qty), 0), COALESCE(SUM(amount), 0)
    INTO v_count, v_amount
    FROM public.orders
    WHERE order_list_id = v_order_list_id;
    
    IF v_count = 0 THEN
        DELETE FROM public.order_list WHERE id = v_order_list_id;
    ELSE
        UPDATE public.order_list
        SET total_count = v_count,
            total_amount = v_amount,
            qr_payment = 'https://qr.sepay.vn/img?acc=0395695023&bank=VPBank&amount=' || v_amount::INTEGER::text || '&des=TKPS2E+DH' || v_order_list_id::text,
            updated_at = now()
        WHERE id = v_order_list_id;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ensure_order_list()
RETURNS TRIGGER AS $$
DECLARE
    v_order_list_id BIGINT;
    v_sum_insured NUMERIC(20,2);
    v_existing_order_id BIGINT;
    v_existing_qty INTEGER;
BEGIN
    IF NEW.order_list_id IS NULL THEN
        INSERT INTO public.infor_user (from_id) VALUES (NEW.from_id) ON CONFLICT (from_id) DO NOTHING;
        
        SELECT id INTO v_order_list_id
        FROM public.order_list
        WHERE from_id = NEW.from_id AND status = 'pending'
        LIMIT 1;
        
        IF v_order_list_id IS NULL THEN
            INSERT INTO public.order_list (from_id, status)
            VALUES (NEW.from_id, 'pending')
            RETURNING id INTO v_order_list_id;
        END IF;
        
        NEW.order_list_id := v_order_list_id;
    END IF;
    
    SELECT id, qty INTO v_existing_order_id, v_existing_qty
    FROM public.orders
    WHERE order_list_id = NEW.order_list_id
      AND insurance_id = NEW.insurance_id
      AND status = 'pending'
    LIMIT 1;
    
    IF v_existing_order_id IS NOT NULL THEN
        SELECT sum_insured INTO v_sum_insured
        FROM public.insurance_products
        WHERE insurance_id = NEW.insurance_id;
        
        UPDATE public.orders 
        SET qty = v_existing_qty + NEW.qty,
            amount = v_sum_insured * (v_existing_qty + NEW.qty)
        WHERE id = v_existing_order_id;
        
        RETURN NULL; 
    END IF;
    
    IF NEW.amount IS NULL OR NEW.amount = 0 THEN
        SELECT sum_insured INTO v_sum_insured
        FROM public.insurance_products
        WHERE insurance_id = NEW.insurance_id;
        
        IF v_sum_insured IS NOT NULL THEN
            NEW.amount := v_sum_insured * NEW.qty;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- << FUNCTION ĐÃ ĐƯỢC SỬA LỖI >>
CREATE OR REPLACE FUNCTION ensure_user_and_update_stats()
RETURNS TRIGGER AS $$
DECLARE
    v_total_insurance INTEGER;
    v_total_amount NUMERIC(20,2);
    v_latest_order_list BIGINT;
    v_user_status TEXT;
BEGIN
    -- Chỉ thực thi logic khi đơn hàng CHUYỂN SANG trạng thái 'completed'
    IF NEW.status = 'completed' AND (OLD IS NULL OR OLD.status IS DISTINCT FROM 'completed') THEN
    
        INSERT INTO public.infor_user (from_id) 
        VALUES (NEW.from_id) 
        ON CONFLICT (from_id) DO NOTHING;
        
        SELECT 
          COUNT(*),
          COALESCE(SUM(ol.total_amount), 0),
          MAX(ol.id)
        INTO v_total_insurance, v_total_amount, v_latest_order_list
        FROM public.order_list ol
        WHERE ol.from_id = NEW.from_id AND ol.status = 'completed';

        IF v_total_amount >= 100000 THEN
            v_user_status := 'vip';
        ELSIF v_total_amount >= 50000 THEN
            v_user_status := 'middle';
        ELSE
            v_user_status := 'new';
        END IF;
        
        UPDATE public.infor_user 
        SET qty_insurance = v_total_insurance,
            total_buy = v_total_amount,
            last_buy = v_latest_order_list,
            status = v_user_status,
            updated_at = now()
        WHERE from_id = NEW.from_id;
        
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION recalc_order_amount()
RETURNS TRIGGER AS $$
DECLARE
    v_sum_insured NUMERIC(20,2);
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.qty IS DISTINCT FROM OLD.qty THEN
        SELECT sum_insured INTO v_sum_insured FROM public.insurance_products WHERE insurance_id = NEW.insurance_id;
        IF v_sum_insured IS NOT NULL THEN
            NEW.amount := v_sum_insured * NEW.qty;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- Tạo bảng để lưu trữ ký ức (memories)
CREATE TABLE IF NOT EXISTS
  public.documents (
    id uuid primary key,
    content text, -- Nội dung ký ức
    metadata jsonb, -- Metadata, quan trọng nhất là user_id
    embedding vector (1536) -- 1536 cho OpenAI embeddings
  );

-- Tạo hàm để tìm kiếm các ký ức tương đồng
create or replace function match_documents (
  query_embedding vector(1536),
  match_count int,
  filter jsonb DEFAULT '{}'
) returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
) 
language plpgsql
as $$
#variable_conflict use_column
begin
  return query
  select
    id,
    content,
    metadata,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where metadata @> filter
  order by documents.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Gán Triggers cho các bảng
DROP TRIGGER IF EXISTS ensure_order_list_trigger ON public.orders;
CREATE TRIGGER ensure_order_list_trigger
    BEFORE INSERT ON public.orders
    FOR EACH ROW EXECUTE FUNCTION ensure_order_list();

DROP TRIGGER IF EXISTS order_update_trigger ON public.orders;
CREATE TRIGGER order_update_trigger
    AFTER INSERT OR UPDATE OR DELETE ON public.orders
    FOR EACH ROW EXECUTE FUNCTION update_order_totals();

-- << TRIGGER ĐÃ ĐƯỢC SỬA LỖI >>
DROP TRIGGER IF EXISTS user_stats_trigger ON public.order_list;
CREATE TRIGGER user_stats_trigger
    AFTER INSERT OR UPDATE ON public.order_list
    FOR EACH ROW -- Xóa WHEN condition
    EXECUTE FUNCTION ensure_user_and_update_stats();

DROP TRIGGER IF EXISTS recalc_order_amount_trigger ON public.orders;
CREATE TRIGGER recalc_order_amount_trigger
    BEFORE UPDATE OF qty ON public.orders
    FOR EACH ROW EXECUTE FUNCTION recalc_order_amount();


-- Chèn dữ liệu sản phẩm mẫu
INSERT INTO public.insurance_products (insurance_name, insurance_type, sum_insured, term) VALUES
('Bảo hiểm sức khỏe Vàng', 'health', 10000.00, '1 năm'),
('Bảo hiểm sức khỏe Kim Cương', 'health', 25000.00, '1 năm'),
('Bảo hiểm du lịch Châu Á', 'travel', 20000.00, '1 tháng'),
('Bảo hiểm du lịch Toàn Cầu', 'travel', 40000.00, '1 tháng'),
('Bảo hiểm xe máy cơ bản', 'motorbike', 5000.00,  '1 năm'),
('Bảo hiểm ô tô hai chiều', 'car', 30000.00, '1 năm'),
('Bảo hiểm nhân thọ An Tâm', 'life', 50000.00, '10 năm'),
('Bảo hiểm tai nạn 24/7', 'personal_accident', 15000.00, '1 năm'),
('Bảo hiểm nhà ở Chung Cư', 'home', 25000.00, '1 năm'),
('Bảo hiểm phi nhân thọ', 'non_life', 10000.00, '1 năm');

-- Cấp quyền
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO PUBLIC;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO PUBLIC;

COMMIT;