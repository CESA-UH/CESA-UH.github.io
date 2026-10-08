"""Explicit local demo: python -m app.seed. Never runs on server startup."""
from datetime import datetime, timedelta
from sqlalchemy import select
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import User, UserRole, Course, Topic, Enrollment, CourseInvite, SelfReport, Resource, ResourceChunk
from app.services.retrieval import chunk_page


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email=='teacher@demo.local')):
            print('Demo already exists; no changes made.')
            return
        password = hash_password('Demo12345!')
        teacher=User(email='teacher@demo.local',password_hash=password,first_name='سارا',last_name='احمدی',role=UserRole.TEACHER)
        db.add(teacher);db.flush()
        students=[]
        for email,first,last in [('student@demo.local','آرمان','رضایی'),('mina@demo.local','مینا','کریمی'),('ali@demo.local','علی','محمدی'),('niloofar@demo.local','نیلوفر','رحمانی')]:
            student=User(email=email,password_hash=password,first_name=first,last_name=last,role=UserRole.STUDENT)
            db.add(student);students.append(student)
        db.flush()
        course=Course(name='مبانی هوش مصنوعی',description='از جستجوی مسئله تا یادگیری ماشین؛ منابع و گزارش‌های این کلاس نمایشی‌اند.',teacher_id=teacher.id)
        db.add(course);db.flush()
        db.add(CourseInvite(course_id=course.id,code='HAMDARS101'))
        names=['جستجوی ناآگاهانه','جستجوی آگاهانه','مسائل ارضای محدودیت','یادگیری نظارت‌شده']
        descriptions=['BFS و DFS، فضای حالت و هزینهٔ مسیر','هیوریستیک، جستجوی حریصانه و A*','متغیرها، دامنه‌ها و محدودیت‌ها','دادهٔ آموزش، تعمیم و بیش‌برازش']
        texts=[
            'جستجوی ناآگاهانه\nدر جستجوی ناآگاهانه، الگوریتم اطلاعاتی دربارهٔ فاصله تا هدف ندارد. جستجوی سطح اول یا BFS گره‌ها را به ترتیب عمق گسترش می‌دهد و از صف استفاده می‌کند. اگر هزینهٔ همهٔ یال‌ها یکسان باشد، BFS کوتاه‌ترین مسیر را پیدا می‌کند. جستجوی عمق اول یا DFS یک شاخه را تا انتها دنبال می‌کند و از پشته استفاده می‌کند. DFS در فضای نامتناهی ممکن است به جواب نرسد. برای مقایسهٔ این دو روش یک درخت کوچک رسم کن و ترتیب بازدید گره‌ها را بنویس.',
            'جستجوی آگاهانه و A*\nجستجوی آگاهانه از دانش مربوط به مسئله برای انتخاب گره بعدی استفاده می‌کند. تابع هیوریستیک h(n) هزینهٔ باقی‌مانده تا هدف را تخمین می‌زند. در الگوریتم A* تابع ارزیابی f(n) = g(n) + h(n) است؛ g(n) هزینهٔ مسیر از شروع تا گره n و h(n) تخمین هزینه تا هدف است. اگر g=3 و h=5 باشد، f=8 است. جستجوی حریصانه فقط h(n) را در نظر می‌گیرد. هیوریستیک قابل قبول هزینهٔ واقعی را بیش‌برآورد نمی‌کند. برای بهینگی جستجوی گراف A* بدون بازگشایی گره‌های بسته، هیوریستیک سازگار لازم است. تمرین: برای سه گره با مقادیر (g,h) برابر (2,5)، (4,2)، (3,6)، مقدار f را محاسبه و گره با کمترین f را انتخاب کن.',
            'مسائل ارضای محدودیت\nیک مسئلهٔ CSP با مجموعه‌ای از متغیرها، دامنهٔ هر متغیر و محدودیت‌ها تعریف می‌شود. در رنگ‌آمیزی نقشه، متغیرها ناحیه‌ها هستند و دامنه رنگ‌هاست. محدودیت می‌گوید دو ناحیهٔ مجاور رنگ یکسان نداشته باشند. روش عقبگرد یا Backtracking مقدارها را امتحان می‌کند و هنگام نقض محدودیت بازمی‌گردد. راهبرد MRV متغیری با کمترین تعداد مقدار مجاز باقی‌مانده را انتخاب می‌کند. پیش‌بررسی دامنهٔ همسایه‌ها را بعد از تخصیص کاهش می‌دهد. برای تمرین سه ناحیهٔ مجاور را با سه رنگ رنگ‌آمیزی و محدودیت‌ها را فهرست کن.',
            'یادگیری نظارت‌شده\nدر یادگیری نظارت‌شده داده‌های آموزش دارای برچسب‌اند. در طبقه‌بندی، خروجی یک دسته است و در رگرسیون خروجی یک مقدار عددی است. داده‌ها را به آموزش، اعتبارسنجی و آزمون تقسیم می‌کنیم. مجموعهٔ آزمون برای ارزیابی نهایی کنار گذاشته می‌شود و نباید برای تنظیم مدل استفاده شود. بیش‌برازش زمانی رخ می‌دهد که مدل روی آموزش خوب عمل می‌کند اما روی دادهٔ جدید عملکرد ضعیفی دارد. منظم‌سازی و انتخاب پیچیدگی مناسب مدل می‌توانند کمک کنند. تمرین: پیش‌بینی قیمت خانه را با تشخیص ایمیل هرزنامه مقایسه کن و نوع مسئله را مشخص کن.'
        ]
        topics=[]
        for name,description,text in zip(names,descriptions,texts):
            topic=Topic(course_id=course.id,name=name,description=description);db.add(topic);db.flush();topics.append(topic)
            resource=Resource(course_id=course.id,topic_id=topic.id,title='جزوهٔ '+name,filename='demo-notes.txt',uploaded_by=teacher.id,page_count=1)
            db.add(resource);db.flush()
            for position,chunk in enumerate(chunk_page(text)):
                db.add(ResourceChunk(resource_id=resource.id,page=1,position=position,text=chunk))
        for student in students:db.add(Enrollment(course_id=course.id,student_id=student.id))
        now=datetime.utcnow()
        for si,student in enumerate(students[:3]):
            for days in range(6,0,-1):
                topic=topics[(days+si)%len(topics)]
                db.add(SelfReport(student_id=student.id,topic_id=topic.id,confidence=2+(days+si)%3,difficulty='concept' if days%2 else 'practice',study_minutes=20+days*5,note='نمونهٔ خوداظهاری برای نمایش روند مطالعه.',created_at=now-timedelta(days=days)))
            for ti,topic in enumerate(topics):
                confidence=([4,2,2,3] if si==0 else [5,4,3,4] if si==1 else [2,3,1,2])[ti]
                db.add(SelfReport(student_id=student.id,topic_id=topic.id,confidence=confidence,difficulty='none' if confidence>=4 else 'practice' if ti==1 else 'concept',study_minutes=10,note='در محاسبهٔ تابع ارزیابی A* نیاز به مثال بیشتر دارم.' if ti==1 and si==0 else 'این داده برای نمایش اولیهٔ سیستم است.',created_at=now-timedelta(minutes=ti*5)))
        db.commit()
    print('Demo ready. Teacher: teacher@demo.local | Student: student@demo.local')
    print('Password: Demo12345! | Course code: HAMDARS101')


if __name__=='__main__':main()
