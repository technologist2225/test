import psycopg2.extras
import math
from data_manager import get_db_connection

def get_all_shops(page=1, limit=10):
    """Hàm phân trang thật: Lấy danh sách shop kèm theo tính toán tổng số trang"""
    conn = get_db_connection()
    if not conn:
        return False, "Lỗi kết nối Cơ sở dữ liệu", None

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # 1. Chạy SQL đếm tổng số cửa hàng đang hoạt động trong hệ thống
        count_query = "SELECT COUNT(*) FROM Shops WHERE IsActive = TRUE;"
        cursor.execute(count_query)
        total_items = cursor.fetchone()['count'] # Lấy ra tổng số dòng
        
        # 2. Tính toán điểm xuất phát (OFFSET) dựa trên số trang truyền vào
        offset = (page - 1) * limit
        
        # 3. Chạy SQL lấy dữ liệu giới hạn bằng LIMIT và OFFSET
        # Sử dụng dấu ngoặc kép để ép giữ đúng chữ hoa chữ thường trả về cho Postman
        data_query = """
            SELECT 
                ShopID AS "ShopID", 
                ShopName AS "ShopName", 
                Address AS "Address", 
                Hotline AS "Hotline", 
                ShopImageURL AS "ShopImageURL", 
                ManagerID AS "ManagerID", 
                IsActive AS "IsActive", 
                CreatedAt AS "CreatedAt"
            FROM Shops
            WHERE IsActive = TRUE
            ORDER BY CreatedAt DESC, "ShopID" ASC
            LIMIT %s OFFSET %s;
        """
        cursor.execute(data_query, (limit, offset))
        shops_list = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # 4. Tính toán tổng số trang có thể có (Dùng hàm làm tròn lên math.ceil)
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 1
        
        # Đóng gói dữ liệu đầu ra rành mạch
        pagination_result = {
            "shops": shops_list,
            "meta": {
                "total_items": total_items,
                "current_page": page,
                "total_pages": total_pages
            }
        }
        return True, "Lấy danh sách cửa hàng thành công", pagination_result
        
    except Exception as e:
        if conn: conn.rollback()
        print("❌ Lỗi SQL Get All Shops Pagination:", str(e))
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None
    
def get_shop_details(shop_id):
    """Hàm lấy thông tin chi tiết của một cửa hàng cụ thể dựa vào ShopID"""
    conn = get_db_connection()
    if not conn:
        return False, "Lỗi kết nối Cơ sở dữ liệu", None

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Bắt buộc dùng ngoặc kép để ép PostgreSQL giữ đúng chữ hoa/thường cho Postman
        # Chỉ lấy shop khi IsActive = TRUE (Shop đang mở cửa)
        sql_query = """
            SELECT 
                ShopID AS "ShopID", 
                ShopName AS "ShopName", 
                Address AS "Address", 
                Hotline AS "Hotline", 
                ShopImageURL AS "ShopImageURL", 
                ManagerID AS "ManagerID", 
                IsActive AS "IsActive", 
                CreatedAt AS "CreatedAt",
                UpdatedAt AS "UpdatedAt"
            FROM Shops
            WHERE ShopID = %s AND IsActive = TRUE;
        """
        # Truyền shop_id vào câu SQL (Lưu ý dấu phẩy trong tuple (shop_id,))
        cursor.execute(sql_query, (shop_id,))
        shop = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if shop:
            return True, "Lấy thông tin chi tiết cửa hàng thành công", shop
        else:
            return False, "Không tìm thấy cửa hàng hoặc cửa hàng đã ngừng hoạt động", None
            
    except Exception as e:
        if conn: conn.rollback()
        print("❌ Lỗi SQL Get Shop Details:", str(e))
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None
    
def create_shop(shop_name, address, hotline, manager_id):
    """Hàm thêm mới cửa hàng VÀ tự động nâng cấp User thành Manager"""
    conn = get_db_connection()
    if not conn:
        return False, "Lỗi kết nối Cơ sở dữ liệu", None

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # --- NHIỆM VỤ 1: TẠO CỬA HÀNG ---
        sql_insert_shop = """
            INSERT INTO Shops (ShopName, Address, Hotline, ManagerID) 
            VALUES (%s, %s, %s, %s) 
            RETURNING 
                ShopID AS "ShopID", 
                ShopName AS "ShopName", 
                Address AS "Address", 
                Hotline AS "Hotline", 
                ShopImageURL AS "ShopImageURL", 
                ManagerID AS "ManagerID", 
                IsActive AS "IsActive", 
                CreatedAt AS "CreatedAt";
        """
        cursor.execute(sql_insert_shop, (shop_name, address, hotline, manager_id))
        new_shop = cursor.fetchone()
        
        # --- NHIỆM VỤ 2: NÂNG CẤP QUYỀN (ROLEID = 2) ---
        # Chỉ nâng cấp nếu người dùng hiện tại đang là Customer (RoleID = 3)
        # Nếu họ đã là Admin (1) hoặc Manager (2) rồi thì giữ nguyên
        sql_update_role = """
            UPDATE Users 
            SET RoleID = 2, UpdatedAt = CURRENT_TIMESTAMP
            WHERE UserID = %s AND RoleID = 3;
        """
        cursor.execute(sql_update_role, (manager_id,))
        
        # QUAN TRỌNG: Lệnh commit() này sẽ chốt sổ CẢ 2 tác vụ cùng một lúc. 
        # Nếu 1 trong 2 bị lỗi, database sẽ tự động hủy bỏ cả hai (Rollback).
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return True, "Tạo cửa hàng và tự động phân quyền Chủ cửa hàng thành công", new_shop
        
    except psycopg2.errors.ForeignKeyViolation:
        if conn: conn.rollback()
        return False, "Mã người quản lý (ManagerID) không tồn tại trong hệ thống", None
    except Exception as e:
        if conn: conn.rollback()
        print("❌ Lỗi SQL Create Shop:", str(e))
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None
    
def update_shop(shop_id, user_id, role_id, shop_name=None, address=None, hotline=None):
    """Hàm cập nhật thông tin cửa hàng có xác thực quyền sở hữu"""
    conn = get_db_connection()
    if not conn:
        return False, "Lỗi kết nối Cơ sở dữ liệu", None

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # --- BƯỚC 1: KIỂM TRA QUYỀN SỞ HỮU ---
        cursor.execute("SELECT ManagerID FROM Shops WHERE ShopID = %s", (shop_id,))
        shop = cursor.fetchone()
        
        if not shop:
            cursor.close(); conn.close()
            return False, "Không tìm thấy cửa hàng", None
            
        # Chặn nếu không phải là Quản lý của shop này VÀ cũng không phải Admin (Role 1)
        if str(shop['managerid']) != str(user_id) and role_id != 1:
            cursor.close(); conn.close()
            return False, "Bạn không có quyền cập nhật cửa hàng này", None

        # --- BƯỚC 2: TIẾN HÀNH CẬP NHẬT ---
        sql_query = """
            UPDATE Shops 
            SET 
                ShopName = COALESCE(%s, ShopName),
                Address = COALESCE(%s, Address),
                Hotline = COALESCE(%s, Hotline)
            WHERE ShopID = %s AND IsActive = TRUE
            RETURNING 
                ShopID AS "ShopID", ShopName AS "ShopName", Address AS "Address", 
                Hotline AS "Hotline", ManagerID AS "ManagerID";
        """
        cursor.execute(sql_query, (shop_name, address, hotline, shop_id))
        updated_shop = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if updated_shop:
            return True, "Cập nhật thông tin cửa hàng thành công", updated_shop
        else:
            return False, "Cửa hàng đã ngừng hoạt động", None
            
    except Exception as e:
        if conn: conn.rollback()
        print("❌ Lỗi SQL Update Shop:", str(e))
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None

def toggle_shop_status(shop_id):
    """Nghiệp vụ Toggle: Tự động đảo ngược trạng thái hoạt động (TRUE <-> FALSE) của cửa hàng"""
    conn = get_db_connection()
    if not conn:
        return False, "Lỗi kết nối Cơ sở dữ liệu", None

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Câu lệnh SQL thần thánh: IsActive = NOT IsActive
        sql_query = """
            UPDATE Shops 
            SET IsActive = NOT IsActive, UpdatedAt = CURRENT_TIMESTAMP
            WHERE ShopID = %s
            RETURNING ShopID AS "ShopID", ShopName AS "ShopName", IsActive AS "IsActive";
        """
        cursor.execute(sql_query, (shop_id,))
        updated_shop = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if updated_shop:
            # Tạo câu thông báo động dựa theo trạng thái mới của cửa hàng
            trang_thai = "Mở cửa hoạt động" if updated_shop["IsActive"] else "Đóng cửa tạm nghỉ"
            return True, f"Đã chuyển trạng thái cửa hàng sang: {trang_thai}", updated_shop
        else:
            return False, "Không tìm thấy cửa hàng để cập nhật trạng thái", None
            
    except Exception as e:
        if conn: conn.rollback()
        print("❌ Lỗi SQL Toggle Shop Status:", str(e))
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None