import tkinter
from PIL import ImageTk



def submit():
    print(entry.get())
    root.destroy()

captcha_file = '0_32_42_test_human.png'
root = tkinter.Tk()
img = ImageTk.PhotoImage(file=captcha_file)
label = tkinter.Label(root, image=img)
label.pack()
entry = tkinter.Entry(root)
entry.pack()
btn = tkinter.Button(root, text='Submit captcha', command=submit)
btn.pack()
root.mainloop()