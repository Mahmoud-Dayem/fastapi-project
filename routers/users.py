from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.auth import create_access_token, decode_token
from app.config import settings
from app.errors import EMAIL_ALREADY_EXIST, USER_ALREADY_EXIST, USER_NOT_FOUND
from database import SessionDep
from models.post import PostModel, PostPublic
from models.user import UserCreate, UserModel, UserPublic

router = APIRouter(prefix="/users", tags=["Users"])

password_hash = PasswordHash.recommended()




# verify new password
def verify_password(plain_passoword: str, hashed_password: str):
    return password_hash.verify(plain_passoword, hashed_password)


# @router.post("/token")
# async def login(
#     session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
# ):

#     print(form_data.username)
#     print(form_data.password)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=UserPublic,
)
async def create_user(
    user: UserCreate,
    session: SessionDep,
):
    # Check if username already exists
    username_result = await session.execute(
        select(UserModel).where(UserModel.username == user.username)
    )

    if username_result.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Creditional Error"
        )

    email_result = await session.execute(
        select(UserModel).where(UserModel.email == user.email)
    )

    if email_result.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Creditional Error"
        )

    # Hash password
    hashed_password = password_hash.hash(user.password)

    # Create database model
    db_user = UserModel(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
    )

    session.add(db_user)

    await session.commit()
    await session.refresh(db_user)

    return db_user


# fetch user based on id
# @router.get(
#     "/{user_id}",
#     response_model=UserPublic,
# )
# async def get_user(
#     user_id: int,
#     session: SessionDep,
# ):
#     user = await session.get(UserModel, user_id)

#     if not user:
#         raise usrenot

#     return user


############################## eager loading vs lazy loading


@router.get(
    "/{user_id}/posts",
    response_model=list[PostPublic],
)
async def get_user_posts(
    user_id: int,
    session: SessionDep,
):

    user = await session.get(
        UserModel, user_id, options=[selectinload(UserModel.posts)]
    )
    if not user:
        raise USER_NOT_FOUND
 

    return user.posts

 

# @router.post("/login")
# async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
#     print("********************************************")
#     print(form_data.username)
#     print(form_data.password)

DUMMY_HASHED_PASSWORD = password_hash.hash("123456")


@router.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
):
    result = await session.execute(
        select(UserModel).where(UserModel.email == form_data.username)
    )

    user = result.scalar_one_or_none()

    if not user:
        password_hash.verify(form_data.password, DUMMY_HASHED_PASSWORD)

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not password_hash.verify(
        form_data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"www-Authenticate": "Beared"},
        )

    token = create_access_token({"sub": user.email, "type": "access_token"})
    return {"access_token": token, "token_type": "bearer", "token": token}


# If correct:
# create JWT access token here


# token = create_access_token({"email": "mahmoud@example.com"})
# token_test = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6Im1haG1vdWRAZXhhbXBsZS5jb20iLCJpYXQiOjE3OTEImV4cCI6MTc5MTQ0NTg5OX0.b2WlgZY1AffjZ7OjJp_frB_Z9C0HWMTrFtd1_Hi-yp0"

# print(f"Token is  {token}")
# verify_token = decode_access_token(token_test)
# print(f"verificaiton is {verify_token}")
