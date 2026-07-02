python -m pip install --upgrade pip

python -m pip install --upgrade git+https://github.com/mtillman14/scistack.git#subdirectory=scicanonicalhash
python -m pip install --upgrade git+https://github.com/mtillman14/scistack.git#subdirectory=path-gen
python -m pip install --upgrade git+https://github.com/mtillman14/scistack.git#subdirectory=scifor
python -m pip install --upgrade git+https://github.com/mtillman14/scistack.git#subdirectory=sciduckdb
python -m pip install --upgrade git+https://github.com/mtillman14/scistack.git#subdirectory=scilineage
python -m pip install --upgrade git+https://github.com/mtillman14/scistack.git#subdirectory=scidb
python -m pip install --upgrade git+https://github.com/mtillman14/scistack.git#subdirectory=scimatlab
python -m pip install --upgrade git+https://github.com/mtillman14/scistack.git#subdirectory=scistack

python -c "import scidb, scifor, scistack; print('SciStack OK')"