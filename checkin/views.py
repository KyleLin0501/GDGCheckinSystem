from django.shortcuts import render

# Create your views here.
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import IntegrityError
from .models import Student, Course, CheckinRecord
import json
from django.utils import timezone
import csv # <--- 引入 csv 模組
from django.utils.encoding import smart_str # 處理中文編碼
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse


def checkin_page(request):
    """
    簽到頁面視圖
    - 取得所有課程以供選擇
    """
    courses = Course.objects.all()
    context = {
        'courses': courses,
    }
    return render(request, 'checkin.html', context)


# 僅接受 POST 請求
@require_POST
# 由於是 AJAX POST 請求，如果沒有表單，需要處理 CSRF token。
# 這裡使用 @csrf_exempt 暫時繞過 CSRF 檢查，
# 但**正式環境中建議在前端 AJAX 請求中加入 CSRF token**。
# 註: 更安全的作法是從 cookies 中取得 CSRF token 並在 AJAX header 中傳遞。
@csrf_exempt
def handle_checkin(request):
    """
    處理 AJAX 傳來的學號和課程 ID，進行簽到操作。
    """
    try:
        # 從 POST 請求中獲取 JSON 資料
        data = json.loads(request.body)
        student_id = data.get('student_id', '').strip()
        course_id = data.get('course_id')

        # 1. 檢查課程是否存在
        try:
            course = Course.objects.get(pk=course_id)
        except Course.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '課程不存在。'}, status=400)

        # 2. 檢查社員是否存在
        try:
            student = Student.objects.get(student_id=student_id)
        except Student.DoesNotExist:
            # 若非社員
            return JsonResponse({
                'status': 'non_member',
                'message': f"學號 {student_id} 非社團成員。"
            }, status=200)

        # 3. 檢查是否已簽到 (利用 unique_together 的限制)
        try:
            # === 修正點：在創建 CheckinRecord 時帶入 member_id ===
            CheckinRecord.objects.create(
                course=course,
                student=student,
                # 將 Student 上的 member_id 複製到 CheckinRecord
                member_id=student.member_id
            )
            # ====================================================

            # 簽到成功 (使用 localtime 確保輸出台北時間)
            local_time = timezone.localtime(timezone.now())

            return JsonResponse({
                'status': 'success',
                'message': '簽到成功！',
                'student_name': student.name,
                'student_id': student.student_id,
                'course_name': course.name,
                # 使用修正後的 local_time
                'time': local_time.strftime('%Y/%m/%d %H:%M:%S')
            })

        except IntegrityError:
            # 重複簽到 (由 unique_together 限制觸發)
            return JsonResponse({
                'status': 'already_checkedin',
                'message': f"社員 {student.name} (學號 {student.student_id}) 已經簽到過了！"
            }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': '無效的 JSON 格式。'}, status=400)
    except Exception as e:
        # 其他伺服器內部錯誤
        return JsonResponse({'status': 'error', 'message': f"伺服器錯誤: {e}"}, status=500)


def export_checkins_csv(request, course_id):
    """
    根據課程 ID 匯出包含所有社員名單和簽到狀態的 CSV 檔案。
    - 依社員編號排序。
    - 包含「是否有簽到記錄」欄位 (1 或 0)。
    """
    course = get_object_or_404(Course, pk=course_id)

    response = HttpResponse(content_type='text/csv')

    # 檔案名稱：包含課程名稱和日期
    filename_date = course.date.strftime('%Y%m%d')
    filename = f"{filename_date}_{course.name}_課程社員簽到總表.csv"
    response['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'%s' % filename.encode('utf-8').decode(
        'iso-8859-1')

    # 3. 創建 CSV writer 物件
    # 設置 encoding='utf-8-sig' 以支持中文並避免 Excel 亂碼
    writer = csv.writer(response, quoting=csv.QUOTE_MINIMAL)

    # 寫入課程資訊標題
    writer.writerow(['課程日期:', course.date.strftime('%Y/%m/%d')])
    writer.writerow(['課程名稱:', course.name])
    writer.writerow([])  # 空白行分隔

    # 4. 寫入 CSV 資料標題 (Header)
    # 修正點：移除 checkin_time，新增 Has_Checked_In
    header = ['社員編號', '社員姓名', '社員學號', '是否有簽到記錄', '實際簽到時間']
    writer.writerow(header)

    # === 核心邏輯修正開始 ===

    # A. 取得該課程的所有簽到記錄，並建立一個快速查詢字典
    # 鍵(key)為 student_id，值(value)為 CheckinRecord 物件
    checkins = CheckinRecord.objects.filter(course=course).select_related('student')

    # 建立字典，方便查詢簽到狀態和時間
    checked_in_students = {
        record.student_id: record for record in checkins
    }

    # B. 取得所有社員，並依 member_id 排序
    # 由於 member_id 允許為 None (null=True)，我們需要處理排序
    # 這裡我們讓 None 值排在最後面 (假設 None/空編號的優先級最低)
    all_students = Student.objects.all().order_by('member_id')

    # C. 遍歷所有社員並輸出資料行
    for student in all_students:

        # 檢查該社員是否在本次課程簽到
        record = checked_in_students.get(student.id)  # 使用 student.id 查詢會更保險

        has_checked_in = 0
        checkin_time_str = ''

        if record:
            has_checked_in = 1
            # 轉換為本地時間並格式化
            local_time = timezone.localtime(record.checkin_time)
            checkin_time_str = local_time.strftime('%Y/%m/%d %H:%M:%S')

        # 處理 member_id 可能為 None 的情況
        member_id = student.member_id if student.member_id is not None else ''

        # 組裝輸出資料行
        row = [
            member_id,
            student.name,
            student.student_id,
            has_checked_in,  # 1 或 0
            checkin_time_str,  # 實際簽到時間 (如果沒有則為空字串)
        ]
        writer.writerow(row)

    return response


def get_checkin_list(request, course_id):
    """
    獲取指定課程的簽到列表，按簽到時間降序 (最新簽到在最前)。
    """
    # 確保課程存在，如果不存在則返回 404
    try:
        course = Course.objects.get(pk=course_id)
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Course not found'}, status=404)

    # 查詢簽到記錄：過濾課程，並按簽到時間降序排序
    checkin_records = CheckinRecord.objects.filter(
        course=course
    ).select_related('student').order_by('-checkin_time')  # 降序排列 (最新在最上)

    data = []

    # 遍歷記錄並格式化輸出
    for i, record in enumerate(checkin_records, 1):
        # 處理 member_id 可能為 None 的情況
        member_id = record.member_id if record.member_id is not None else ''

        # 轉換為台北本地時間
        local_time = timezone.localtime(record.checkin_time)

        data.append({
            # 順序編號，因為是倒序排列，這裡的 i 只是方便計數
            'index': i,
            'member_id': member_id,
            'name': record.student.name,
            'student_id': record.student.student_id,
            'checkin_time': local_time.strftime('%Y/%m/%d %H:%M:%S'),
        })

    return JsonResponse({'checkins': data})
