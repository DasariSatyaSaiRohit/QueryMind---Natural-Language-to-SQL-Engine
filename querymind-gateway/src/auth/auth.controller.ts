import {
  Controller,
  Post,
  Get,
  Put,
  Body,
  Request,
  UseGuards,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiBearerAuth,
  ApiResponse,
} from '@nestjs/swagger';
import { AuthService } from './auth.service';
import { UsersService } from '../users/users.service';
import {
  RegisterRequestDto,
  LoginRequestDto,
  RefreshTokenDto,
  UpdateProfileRequestDto,
} from './dto/auth.dto';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { JwtPayload } from './strategies/jwt.strategy';

interface AuthenticatedRequest {
  user: JwtPayload;
  headers: Record<string, string>;
}

@ApiTags('auth')
@Controller('api/v1')
export class AuthController {
  constructor(
    private authService: AuthService,
    private usersService: UsersService,
  ) {}

  @Post('auth/register')
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({ summary: 'Register a new user' })
  @ApiResponse({ status: 201, description: 'User registered successfully' })
  @ApiResponse({ status: 400, description: 'Validation failed' })
  @ApiResponse({ status: 409, description: 'Email already registered' })
  async register(@Body() body: RegisterRequestDto) {
    try{
    const { tokens, user } = await this.authService.register(body);
    
    return {
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
      user: {
        user_id: user.user_id,
        email: user.email,
        created_at: user.created_at,
      },
    };
  }catch(error){
    throw error;
  }
  }

  @Post('auth/login')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Login with email and password' })
  @ApiResponse({ status: 200, description: 'Login successful' })
  @ApiResponse({ status: 401, description: 'Invalid credentials' })
  async login(@Body() body: LoginRequestDto) {
    const { tokens, user } = await this.authService.login(body);
    return {
      tokens:{access_token: tokens.access_token,
      refresh_token: tokens.refresh_token},
      user: {
        user_id: user.user_id,
        email: user.email,
        created_at: user.created_at,
      },
    };
  }

  @Post('auth/refresh')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Refresh access token' })
  @ApiResponse({ status: 200, description: 'Tokens refreshed' })
  @ApiResponse({ status: 401, description: 'Invalid refresh token' })
  async refresh(@Body() body: RefreshTokenDto) {
    const tokens = await this.authService.refresh(body.refresh_token);
    return {
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
    };
  }

  @Get('users/profile')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Get authenticated user profile' })
  @ApiResponse({ status: 200, description: 'Profile retrieved' })
  @ApiResponse({ status: 401, description: 'Unauthorized' })
  async getProfile(@Request() req: AuthenticatedRequest) {
    const user = await this.usersService.findById(req.user.user_id);
    return {
      user_id: user?.user_id,
      email: user?.email,
      created_at: user?.created_at,
    };
  }

  @Put('users/profile')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Update authenticated user profile' })
  @ApiResponse({ status: 200, description: 'Profile updated' })
  @ApiResponse({ status: 401, description: 'Unauthorized' })
  async updateProfile(
    @Body() body: UpdateProfileRequestDto,
    @Request() req: AuthenticatedRequest,
  ) {
    await this.usersService.updateUser(req.user.user_id, body);
    return { message: 'Profile updated' };
  }
}
