import tkinter
from PIL import ImageTk
import sys



def submit():
    print(entry.get())
    root.destroy()

print(sys.path)
captcha_file = 'test_human.png'
root = tkinter.Tk()
img = ImageTk.PhotoImage(file=captcha_file)
label = tkinter.Label(root, image=img)
label.pack()
entry = tkinter.Entry(root)
entry.pack()
btn = tkinter.Button(root, text='Submit captcha', command=submit)
btn.pack()
root.mainloop()