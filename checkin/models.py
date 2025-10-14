from django.db import models
from django.utils import timezone


class Student(models.Model):
    """社員資料模型"""

    # 社員編號 (數字) - 保持不變
    member_id = models.IntegerField(
        unique=True,
        verbose_name="社員編號",
        help_text="社團內部編號，請使用數字",
        null=True,  # 允許資料庫欄位為 NULL
        blank=True  # 允許 Django 表單為空
    )

    student_id = models.CharField(max_length=15, unique=True, verbose_name="學號")
    name = models.CharField(max_length=100, verbose_name="姓名")

    def __str__(self):
        # 由於 member_id 可能為 None，使用 if-else 處理顯示
        mid_str = f"[{self.member_id}] " if self.member_id is not None else ""
        return f"{mid_str}{self.student_id} - {self.name}"

    class Meta:
        verbose_name = "社員"
        verbose_name_plural = "社員"


class Course(models.Model):
    """社課課程資料模型"""
    date = models.DateField(default=timezone.now, verbose_name="課程日期")
    name = models.CharField(max_length=200, verbose_name="課程名稱")
    classroom = models.CharField(max_length=50, verbose_name="社課教室")

    def __str__(self):
        return f"[{self.date}] {self.name}"

    class Meta:
        ordering = ['-date']  # 依日期降序排列
        verbose_name = "課程"
        verbose_name_plural = "課程"


class CheckinRecord(models.Model):
    """社員簽到記錄模型"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="課程")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="社員")

    # === 新增欄位：社員編號 (冗餘儲存) ===
    member_id = models.IntegerField(
        verbose_name="社員編號",
        null=True,
        blank=True
    )
    # ====================================

    checkin_time = models.DateTimeField(default=timezone.now, verbose_name="簽到時間")

    def __str__(self):
        return f"{self.student.name} 簽到於 {self.course.name} ({self.checkin_time.strftime('%H:%M')})"

    class Meta:
        # 限制：一堂課同一位社員不可重復簽到
        unique_together = ('course', 'student')
        verbose_name = "簽到記錄"
        verbose_name_plural = "簽到記錄"
        ordering = ['-checkin_time']