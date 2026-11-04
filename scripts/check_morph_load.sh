#p=/mnt/c/tmp/RML/build/Source/nlp_base/test_lem/RelWithDebInfo/test_lem.exe
p=/mnt/c/tmp/RML/out/build/x64-Release/Source/nlp_base/TestLem/TestLem.exe

for i in `seq 1 10`; do 
    echo $i
    for l in Russian English German; do
        f=C:/tmp/RML/Source/nlp_base/TestLem/test/$l/test.txt 
        $p --language $l --input $f --output $f.tmp
    done
done