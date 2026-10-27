FROM python:3.12.16-alpine
RUN apk add --no-cache --upgrade 'ca-certificates>=20261020-r0' && update-ca-certificates
RUN python -m pip install --no-cache-dir 'pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'
RUN ! command -v node && ! command -v php
WORKDIR /site
COPY . /site
RUN python check_tls_trust.py
EXPOSE 8080
CMD ["sh", "-c", "python -m http.server ${PORT:-8080} --bind 0.0.0.0"]
