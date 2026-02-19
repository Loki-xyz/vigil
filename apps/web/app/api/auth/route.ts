import { NextResponse } from "next/server"

export async function POST(request: Request) {
  try {
    const { password } = await request.json()
    const correctPassword = process.env.VIGIL_ACCESS_PASSWORD

    if (!correctPassword) {
      return NextResponse.json(
        { success: false, error: "Password not configured" },
        { status: 500 }
      )
    }

    if (password === correctPassword) {
      const response = NextResponse.json({ success: true })
      response.cookies.set("vigil-auth", "authenticated", {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 60 * 60 * 24 * 30, // 30 days
        path: "/",
      })
      return response
    }

    return NextResponse.json({ success: false }, { status: 401 })
  } catch {
    return NextResponse.json(
      { success: false, error: "Invalid request" },
      { status: 400 }
    )
  }
}
