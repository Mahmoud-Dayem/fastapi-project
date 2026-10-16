from fastapi import HTTPException, status

USER_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="User not found",
)

ROOM_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Roomn not found",
)

BOOKING_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Booking not found",
)

SERVICE_UNDER_MAINTENANCE = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="SERVICE IS UNDER MAINTENANC TRY AGAIN LATER",
)

EMAIL_ALREADY_EXIST = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Email already exists",
)
USER_ALREADY_EXIST = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="USER already exists",
)
