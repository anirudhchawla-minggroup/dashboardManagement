from django.shortcuts import render, redirect
from django.contrib.auth.hashers import check_password
from users.models import UserModel

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        try:
            print("reached")
            print(username)
            print(password)
            # Check if the user exists in the database
            user = UserModel.objects.get(username=username,password=password, is_active=True, is_deleted=False)
            # Check password
            if user is not None:
                print("correct")
                # Add username to the session
                request.session['username'] = username
                return render(request, 'dashboard/dashboard.html', {'username': username})
            else:
                return render(request, 'users/login.html', {'error': 'Invalid username or password.'})
        except UserModel.DoesNotExist:
            return render(request, 'users/login.html', {'error': 'User does not exist or is inactive.'})
    
    return render(request, 'users/login.html')
