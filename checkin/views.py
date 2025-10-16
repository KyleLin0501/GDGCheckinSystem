# checkin/views.py

from django.shortcuts import render, redirect # <-- 確保有這個匯入
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt # 【已修正】: 引入 csrf_exempt
from django.views.decorators.http import require_POST # 【已修正】: 引入 require_POST
from django.utils import timezone
import json
import csv
from google.cloud import firestore
from google.cloud.firestore import FieldFilter, And

# 引入您的 Firebase 初始化模組
from . import firebase_init
from datetime import datetime # 確保有這個匯入

def checkin_page(request):
    """
    簽到頁面視圖 - 取得所有課程以供選擇 (使用 Firestore)
    """
    # 在函數內取得 db 客戶端
    db = firebase_init.get_firestore_client()

    if not db:
        return render(request, 'checkin.html', {'courses': []})

    courses_list = []
    try:
        # 查詢 'courses' collection，並依日期降序排序
        courses_ref = db.collection('courses').order_by('date', direction=firestore.Query.DESCENDING).stream()

        for doc in courses_ref:
            data = doc.to_dict()
            course_date = data.get('date')

            courses_list.append({
                'id': doc.id,
                # Django 模板可以處理 datetime 物件
                'date': course_date,
                'name': data.get('name'),
                'classroom': data.get('classroom'),
            })

    except Exception as e:
        print(f"載入課程失敗: {e}")

    context = {
        'courses': courses_list,
    }
    return render(request, 'checkin.html', context)


@csrf_exempt
@require_POST
def handle_checkin(request, *args, **kwargs):
    from google.cloud import firestore
    from django.utils import timezone
    import json
    from . import firebase_init

    db = firebase_init.get_firestore_client()
    if not db:
        return JsonResponse({'status': 'error', 'message': 'Firebase 未初始化'}, status=500)

    try:
        data = json.loads(request.body)
        student_id_input = data.get('student_id', '').strip()
        course_id = data.get('course_id', '').strip()

        # ✅ 驗證 course 存在
        course_ref = db.collection('courses').document(course_id)
        course_doc = course_ref.get()
        if not course_doc.exists:
            return JsonResponse({'status': 'error', 'message': '課程不存在'}, status=400)
        course_data = course_doc.to_dict()
        course_name = course_data.get('name')

        # ✅ 查詢 student
        students_ref = db.collection('students').where('student_id', '==', student_id_input).limit(1)
        students_docs = list(students_ref.stream())

        if not students_docs:
            return JsonResponse({
                'status': 'non_member',
                'message': f'學號 {student_id_input} 非社團成員'
            }, status=200)

        student_doc = students_docs[0]
        student_data = student_doc.to_dict()
        student_name = student_data.get('name')
        member_id = student_data.get('member_id')
        student_email = student_data.get('email', '') # 【新增】: 取得 Email

        # ✅ 查詢是否重複簽到
        checkin_ref = db.collection('checkin_records') \
            .where('course_id', '==', course_id) \
            .where('student_id', '==', student_id_input) \
            .limit(1)
        checkin_docs = list(checkin_ref.stream())

        if checkin_docs:
            return JsonResponse({
                'status': 'already_checkedin',
                'message': f'社員 {student_name} 已簽到過'
            }, status=200)

        # ✅ 建立簽到紀錄
        local_time = timezone.localtime(timezone.now())
        db.collection('checkin_records').add({
            'course_id': course_id,
            'student_id': student_id_input,
            'student_name': student_name,
            'member_id': member_id,
            'student_email': student_email, # 【新增】: 將 Email 寫入簽到記錄
            'checkin_time': local_time,
        })

        return JsonResponse({
            'status': 'success',
            'message': '簽到成功！',
            'student_name': student_name,
            'student_id': student_id_input,
            'course_name': course_name,
            'time': local_time.strftime('%Y/%m/%d %H:%M:%S'),
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON 格式錯誤'}, status=400)
    except Exception as e:
        print("簽到錯誤:", e)
        return JsonResponse({'status': 'error', 'message': f'伺服器錯誤：{e}'}, status=500)


def export_checkins_csv(request, course_id):
    """
    根據課程 ID 匯出包含所有社員名單和簽到狀態的 CSV 檔案 (使用 Firestore)。
    """
    db = firebase_init.get_firestore_client()

    if not db:
        return HttpResponse("伺服器錯誤：Firebase 客戶端未載入。", status=500)

    # 1. 取得課程資訊
    course_doc = db.collection('courses').document(course_id).get()
    if not course_doc.exists:
        return HttpResponse("課程不存在", status=404)
    course_data = course_doc.to_dict()

    course_name = course_data.get('name', '未知課程')

    # 處理日期物件
    course_date_obj = course_data.get('date')
    if course_date_obj:
        course_date_str = course_date_obj.strftime('%Y/%m/%d')
        filename_date = course_date_obj.strftime('%Y%m%d')
    else:
        course_date_str = '未知日期'
        filename_date = 'NODATE'

    response = HttpResponse(content_type='text/csv')

    # 檔案名稱：包含課程名稱和日期
    filename = f"{filename_date}_{course_name}_課程社員簽到總表.csv"
    response['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'%s' % filename.encode('utf-8').decode(
        'iso-8859-1')

    # 創建 CSV writer 物件
    writer = csv.writer(response, quoting=csv.QUOTE_MINIMAL)

    # 寫入課程資訊標題
    writer.writerow(['課程日期:', course_date_str])
    writer.writerow(['課程名稱:', course_name])
    writer.writerow([])

    # 寫入 CSV 資料標題 (Header)
    # 【修改】: 新增 Email 欄位
    header = ['社員編號', '社員姓名', '社員學號', 'Email', '是否有簽到記錄', '實際簽到時間']
    writer.writerow(header)

    # 2. 取得該課程的所有簽到記錄，並建立一個快速查詢字典
    checkins_ref = db.collection('checkin_records').where(
        filter=FieldFilter('course_id', '==', course_id)
    ).stream()

    # 鍵為 student_id，值為 record 字典
    checked_in_students = {
        record.to_dict().get('student_id'): record.to_dict()
        for record in checkins_ref
    }

    # 3. 取得所有社員，並依 member_id 排序
    all_students_ref = db.collection('students').order_by('member_id').stream()

    # 4. 遍歷所有社員並輸出資料行
    for student_doc in all_students_ref:
        student = student_doc.to_dict()
        student_id = student.get('student_id')
        member_id = student.get('member_id') if student.get('member_id') is not None else ''
        student_email = student.get('email', '') # 【新增】: 取得 Email

        record = checked_in_students.get(student_id)

        has_checked_in = 0
        checkin_time_str = ''

        if record:
            has_checked_in = 1
            # 轉換為本地時間並格式化
            local_time = timezone.localtime(record.get('checkin_time'))
            checkin_time_str = local_time.strftime('%Y/%m/%d %H:%M:%S')

        # 組裝輸出資料行
        row = [
            member_id,
            student.get('name'),
            student_id,
            student_email, # 【新增】: 加入 Email 欄位
            has_checked_in,  # 1 或 0
            checkin_time_str,  # 實際簽到時間 (如果沒有則為空字串)
        ]
        writer.writerow(row)

    return response


def get_checkin_list(request, course_id):
    """
    獲取指定課程的簽到列表，按簽到時間降序 (最新簽到在最前) (使用 Firestore)。
    """
    db = firebase_init.get_firestore_client()

    if not db:
        return JsonResponse({'error': '伺服器錯誤：Firebase 客戶端未載入。'}, status=500)

    # 檢查課程是否存在 (非必須，但確保流程完整性)
    if not db.collection('courses').document(course_id).get().exists:
        return JsonResponse({'error': 'Course not found'}, status=404)

    data = []
    try:
        # 查詢簽到記錄：過濾課程，並按簽到時間降序排序
        checkin_records_ref = db.collection('checkin_records').where(
            filter=FieldFilter('course_id', '==', course_id)
        ).order_by(
            'checkin_time', direction=firestore.Query.DESCENDING
        ).stream()

        # 遍歷記錄並格式化輸出
        for i, record_doc in enumerate(checkin_records_ref, 1):
            record = record_doc.to_dict()

            # 處理 member_id
            member_id = record.get('member_id') if record.get('member_id') is not None else ''

            # 轉換為台北本地時間 (假設 record.get('checkin_time') 是 datetime 物件)
            local_time = timezone.localtime(record.get('checkin_time'))

            data.append({
                'index': i,
                'member_id': member_id,
                'name': record.get('student_name'),
                'student_id': record.get('student_id'),
                # 'email': record.get('student_email'), # 簽到列表通常不顯示 email，故保持現狀
                'checkin_time': local_time.strftime('%Y/%m/%d %H:%M:%S'),
            })

    except Exception as e:
        # 捕獲查詢錯誤 (例如索引未建立)
        print(f"查詢簽到列表時發生錯誤: {e}")
        return JsonResponse({'error': f'查詢簽到列表失敗: {e}'}, status=500)

    return JsonResponse({'checkins': data})


# --- 頁面讀取視圖 ---

def management_page(request):
    """
    管理頁面：獲取並列出所有社員和課程
    """
    db = firebase_init.get_firestore_client()
    if not db:
        return render(request, 'management.html', {'students': [], 'courses': []})

    students_list = []
    courses_list = []

    try:
        # 1. 獲取所有社員，依 member_id 排序
        students_ref = db.collection('students').order_by('member_id').stream()
        for doc in students_ref:
            data = doc.to_dict()
            students_list.append({
                'id': doc.id,
                'student_id': data.get('student_id', 'N/A'),
                'name': data.get('name', 'N/A'),
                'member_id': data.get('member_id', '-'),
                'email': data.get('email', 'N/A'), # 【新增】: 載入 Email 欄位
            })

        # 2. 獲取所有課程，依日期降序排序
        courses_ref = db.collection('courses').order_by('date', direction=firestore.Query.DESCENDING).stream()
        for doc in courses_ref:
            data = doc.to_dict()
            course_date = data.get('date')
            date_str = course_date.strftime('%Y/%m/%d') if course_date else 'N/A'

            courses_list.append({
                'id': doc.id,
                'date': date_str,  # 傳遞格式化的日期字串給前端顯示
                'name': data.get('name', 'N/A'),
                'classroom': data.get('classroom', '-'),
            })

    except Exception as e:
        print(f"載入管理數據失敗: {e}")

    context = {
        'students': students_list,
        'courses': courses_list,
    }
    return render(request, 'management.html', context)


# --- 資料新增視圖 ---

@csrf_exempt
@require_POST
def add_student(request):
    """
    處理新增社員的 POST 請求
    """
    db = firebase_init.get_firestore_client()
    if not db:
        return HttpResponse('Firebase 連線錯誤。', status=500)

    try:
        student_id = request.POST.get('student_id', '').strip()
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip() # 【新增】: 取得 Email
        member_id_str = request.POST.get('member_id', '').strip()
        member_id = int(member_id_str) if member_id_str.isdigit() else None

        if not student_id or not name or not email: # 【修改】: Email 為必填
            return HttpResponse("學號、姓名和 Email 為必填項。", status=400)

        # 1. 檢查學號是否已存在
        student_query = db.collection('students').where(
            filter=FieldFilter('student_id', '==', student_id)
        ).limit(1)

        if list(student_query.stream()):
            return HttpResponse(f"學號 {student_id} 已存在。", status=400)

        # 2. 檢查社員編號是否已存在 (如果提供了 member_id)
        if member_id is not None:
            member_query = db.collection('students').where(
                filter=FieldFilter('member_id', '==', member_id)
            ).limit(1)
            if list(member_query.stream()):
                return HttpResponse(f"社員編號 {member_id} 已被使用。", status=400)

        student_data = {
            'student_id': student_id,
            'name': name,
            'email': email, # 【新增】: 寫入 Email
            'member_id': member_id,
        }
        db.collection('students').add(student_data)

        return redirect('management_page')

    except Exception as e:
        print(f"新增社員失敗: {e}")
        return HttpResponse(f"伺服器錯誤: {e}", status=500)


@csrf_exempt
@require_POST
def add_course(request):
    """
    處理新增課程的 POST 請求
    """
    db = firebase_init.get_firestore_client()
    if not db:
        return HttpResponse('Firebase 連線錯誤。', status=500)

    try:
        course_name = request.POST.get('name', '').strip()
        classroom = request.POST.get('classroom', '').strip()
        date_str = request.POST.get('date', '').strip()  # date_str 格式為 YYYY-MM-DD

        if not course_name or not date_str:
            return HttpResponse("課程名稱和日期為必填項。", status=400)

        course_date = datetime.strptime(date_str, '%Y-%m-%d')

        course_data = {
            'name': course_name,
            'classroom': classroom,
            'date': course_date,
        }
        db.collection('courses').add(course_data)

        return redirect('management_page')

    except ValueError:
        return HttpResponse("日期格式錯誤，請使用 YYYY-MM-DD 格式。", status=400)
    except Exception as e:
        print(f"新增課程失敗: {e}")
        return HttpResponse(f"伺服器錯誤: {e}", status=500)


# --- 資料編輯/刪除視圖 (透過 AJAX/POST) ---

@csrf_exempt
@require_POST
def update_data(request):
    """
    處理社員或課程的編輯更新請求
    """
    db = firebase_init.get_firestore_client()
    if not db:
        return HttpResponse('Firebase 連線錯誤。', status=500)

    try:
        doc_type = request.POST.get('doc_type')
        doc_id = request.POST.get('doc_id')

        if doc_type not in ['student', 'course'] or not doc_id:
            return HttpResponse('無效的數據類型或 ID。', status=400)

        update_data = {}

        if doc_type == 'student':
            update_data = {
                'name': request.POST.get('name').strip(),
                'student_id': request.POST.get('student_id').strip(),
                'email': request.POST.get('email').strip(), # 【新增】: 取得 Email
            }
            member_id_str = request.POST.get('member_id', '').strip()
            update_data['member_id'] = int(member_id_str) if member_id_str.isdigit() else None

        elif doc_type == 'course':
            date_str = request.POST.get('date').strip()
            course_date = datetime.strptime(date_str, '%Y-%m-%d')

            update_data = {
                'name': request.POST.get('name').strip(),
                'date': course_date,
                'classroom': request.POST.get('classroom', '').strip(),
            }

        db.collection(doc_type + 's').document(doc_id).update(update_data)

        # 成功後返回 200 OK，前端 JS 會處理刷新
        return HttpResponse('更新成功', status=200)

    except ValueError:
        return HttpResponse('數據格式錯誤，請檢查日期或數字欄位。', status=400)
    except Exception as e:
        print(f"更新數據失敗: {e}")
        return HttpResponse(f'伺服器錯誤: {e}', status=500)


@csrf_exempt
@require_POST
def delete_data(request):
    """
    處理社員或課程的刪除請求 (AJAX)
    """
    db = firebase_init.get_firestore_client()
    if not db:
        return JsonResponse({'status': 'error', 'message': 'Firebase 連線錯誤。'}, status=500)

    try:
        doc_type = request.POST.get('doc_type')
        doc_id = request.POST.get('doc_id')

        if doc_type not in ['student', 'course'] or not doc_id:
            return JsonResponse({'status': 'error', 'message': '無效的請求數據。'}, status=400)

        db.collection(doc_type + 's').document(doc_id).delete()

        return JsonResponse({'status': 'success', 'message': f'{doc_type} 刪除成功。'})

    except Exception as e:
        print(f"刪除數據失敗: {e}")
        return JsonResponse({'status': 'error', 'message': f'伺服器錯誤: {e}'}, status=500)