eren@raspberry:~/Desktop/project $ python setup.py

============================================================
Face Recognition System - Setup Utility
============================================================

[DETECTED] Linux System (Generic)
Installing dependencies for Linux...

[STEP 1] Creating virtual environment...
Traceback (most recent call last):
  File "/home/eren/Desktop/project/setup.py", line 122, in <module>
    main()
  File "/home/eren/Desktop/project/setup.py", line 93, in main
    if run_command("python3 -m venv venv"):
  File "/home/eren/Desktop/project/setup.py", line 17, in run_command
    subprocess.check_call(cmd, shell=shell)
  File "/usr/lib/python3.9/subprocess.py", line 368, in check_call
    retcode = call(*popenargs, **kwargs)
  File "/usr/lib/python3.9/subprocess.py", line 349, in call
    with Popen(*popenargs, **kwargs) as p:
  File "/usr/lib/python3.9/subprocess.py", line 951, in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
  File "/usr/lib/python3.9/subprocess.py", line 1823, in _execute_child
    raise child_exception_type(errno_num, err_msg, err_filename)
FileNotFoundError: [Errno 2] No such file or directory: 'python3 -m venv venv'
