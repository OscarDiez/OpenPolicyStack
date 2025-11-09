# Data Delivering

The ```data_delivering.py``` will contain classes and functions for delivering the evaluation results through various channels. For now, the only delivery channel is email, defined by the ```GMailDeliverer``` class. 

The email is delivered through a gmail account:

- Username: cnect.c2.monitor@gmail.com
- Password:uhuhuwehufh&%fjif"
- Client ID: 865300728349-j3h4chiepcl75vqivf6f75cmpuscg4lo.apps.googleusercontent.com
- Client Secret: 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


The current session is stored in the ```google_credentials.json``` and the ```toke.json``` file. 


The class also allows to attach files to the email.  If the credentials are out of date, you need to go through an authentification procedure in your browser. This works if you run the scheduler through the terminal in VS Code which is connected to the EC2 instance via ssh.
