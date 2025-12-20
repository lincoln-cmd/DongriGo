import re
from django import template

register = template.Library()

@register.filter
def cld_transform(url, transforms: str):
    """
    Cloudinary URL의 /image/upload/ 뒤에 변환 옵션을 삽입한다.
    예) .../image/upload/v123/x.jpg
      -> .../image/upload/w_96,h_64,c_fill,q_auto,f_auto/v123/x.jpg
    """
    if not url or "/image/upload/" not in url:
        return url

    # 이미 변환이 들어간 경우(중복 삽입 방지)
    if re.search(r"/image/upload/[^/]+/", url) and ("w_" in url or "c_" in url or "q_" in url or "f_" in url):
        return url

    return url.replace("/image/upload/", f"/image/upload/{transforms}/", 1)
