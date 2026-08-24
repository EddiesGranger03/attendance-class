# 📋 Sổ Điểm Danh Lớp Học — Fullstack Backend (FastAPI + PostgreSQL)

Hệ thống quản lý điểm danh và tính học phí tự động dành riêng cho Giáo viên với kiến trúc Client-Server REST API hiện đại.

---

## 🛠 Tech Stack

| Thành phần | Công nghệ |
|---|---|
| **Frontend** | HTML5, Modern Vanilla CSS (Glassmorphism Dark Theme), Vanilla JS (Fetch API) |
| **Backend** | **Python 3.10+ & FastAPI** |
| **Database** | **PostgreSQL 16** (kèm cơ chế tự động SQLite Fallback khi dev local) |
| **ORM** | **SQLAlchemy 2.0** |
| **Data Validation** | **Pydantic v2** |
| **Authentication** | **JWT (JSON Web Token)** + Bcrypt Password Hashing |
| **Deployment / Container** | **Docker & Docker Compose** |
| **IDE / Debugging** | **VS Code** (kèm file cấu hình `launch.json`) |
| **Database GUI** | **DBeaver** |

---

## 🚀 Hướng Dẫn Khởi Chạy Nhanh

### Cách 1: Chạy trọn gói bằng Docker Compose (Khuyên dùng)

Đảm bảo bạn đã mở **Docker Desktop**, sau đó mở terminal tại thư mục gốc của project và gõ:

```bash
docker compose up --build
```

* **Trang web ứng dụng**: [http://localhost:8000](http://localhost:8000)
* **Tài liệu Swagger API**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc API**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### Cách 2: Chạy trực tiếp với Python Local

1. Mở Terminal / PowerShell tại thư mục `backend`:
   ```bash
   cd backend
   ```
2. Cài đặt các thư viện cần thiết:
   ```bash
   pip install -r requirements.txt
   ```
3. Chạy Server FastAPI với Uvicorn:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
4. Mở trình duyệt truy cập:
   * [http://127.0.0.1:8000](http://127.0.0.1:8000) hoặc mở trực tiếp file `diem-danh-lop-hoc.html`.

*(Lưu ý: Nếu bạn chưa bật PostgreSQL server ở local, backend sẽ tự động kích hoạt SQLite `attendance.db` để bạn có thể test ngay lập tức mà không gặp bất kỳ lỗi nào).*

---

## 🗄️ Hướng Dẫn Kết Nối Database Bằng DBeaver

Khi chạy qua Docker Compose, cơ sở dữ liệu PostgreSQL mở cổng `5432` ra máy tính của bạn:

1. Mở phần mềm **DBeaver** -> Chọn biểu tượng **New Database Connection (Plug icon)**.
2. Chọn **PostgreSQL** -> Nhấn **Next**.
3. Điền thông số kết nối:
   * **Host**: `localhost`
   * **Port**: `5432`
   * **Database**: `attendance_db`
   * **Username**: `postgres`
   * **Password**: `postgres123`
4. Bấm **Test Connection ...** -> Khi hiện thông báo *Connected* -> Nhấn **Finish**.
5. Bạn có thể xem và quản lý trực tiếp các bảng:
   * `users` (Danh sách giáo viên, mật khẩu đã mã hóa bcrypt).
   * `classrooms` (Danh sách lớp học).
   * `students` (Danh sách học sinh và giá học phí).
   * `attendance_sessions` (Lịch sử các buổi điểm danh và tổng doanh thu).
   * `attendance_records` (Chi tiết trạng thái có mặt/vắng mặt của từng học sinh).

---

## 💻 Hướng Dẫn Debug Trong VS Code

Trong thư mục dự án đã có sẵn cấu hình `.vscode/launch.json`:
1. Mở project trong **VS Code**.
2. Nhấn phím tắt `Ctrl + Shift + D` (hoặc mở tab **Run & Debug** ở thanh bên trái).
3. Chọn cấu hình **`FastAPI: Run & Debug Backend`**.
4. Nhấn **F5** để khởi chạy server ở chế độ Debug (có thể đặt Breakpoint, xem biến runtime, debug API).

---

## 📡 Danh Sách API Endpoints

### 1. Xác thực Giáo viên (`/api/auth`)
* `POST /api/auth/register`: Đăng ký tài khoản giáo viên mới.
* `POST /api/auth/login`: Đăng nhập nhận JWT Token.
* `GET /api/auth/me`: Lấy thông tin cá nhân giáo viên.

### 2. Lớp học (`/api/classes`)
* `GET /api/classes`: Lấy danh sách lớp học của giáo viên.
* `POST /api/classes`: Tạo lớp học mới.
* `GET /api/classes/{class_id}`: Xem chi tiết và thống kê doanh thu lớp.
* `PUT /api/classes/{class_id}`: Đổi tên lớp học.
* `DELETE /api/classes/{class_id}`: Xóa lớp học.

### 3. Học sinh (`/api/classes/{class_id}/students`)
* `GET /api/classes/{class_id}/students`: Danh sách học sinh trong lớp.
* `POST /api/classes/{class_id}/students`: Thêm học sinh (tên, học phí/buổi).
* `PUT /api/classes/{class_id}/students/{student_id}`: Sửa tên/học phí.
* `DELETE /api/classes/{class_id}/students/{student_id}`: Xóa học sinh khỏi lớp.

### 4. Điểm danh & Lịch sử (`/api/classes/{class_id}/sessions`)
* `GET /api/classes/{class_id}/sessions`: Xem lịch sử điểm danh và doanh thu từng buổi.
* `GET /api/classes/{class_id}/daily/{target_date}`: Lấy trạng thái điểm danh theo ngày.
* `POST /api/classes/{class_id}/sessions`: Lưu buổi điểm danh (tự động tính tổng tiền).
* `DELETE /api/classes/{class_id}/sessions/{session_id}`: Xóa buổi điểm danh.
